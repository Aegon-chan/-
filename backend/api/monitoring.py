"""监测数据 REST API 端点。

包含站点管理、数据查询、数据上传、数据删除等功能。
"""
from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analysis.monitoring_importer import (
    get_template_columns,
    import_from_file,
    preview_import,
)
from backend.analysis.monitoring_service import (
    DATA_TYPES,
    batch_cleanup as service_batch_cleanup,
    count_station_data_by_type,
    create_station as service_create_station,
    delete_measurements as service_delete_measurements,
    delete_station as service_delete_station,
    get_latest as service_get_latest,
    get_statistics as service_get_statistics,
    get_station as service_get_station,
    get_station_by_code,
    get_summary as service_get_summary,
    list_stations as service_list_stations,
    query_measurements as service_query_measurements,
    update_station as service_update_station,
)
from backend.db.monitoring_session import get_monitoring_session
from backend.schemas.monitoring import (
    CleanupRequest,
    CleanupResponse,
    DataQueryResponse,
    DeleteResponse,
    LatestResponse,
    StatisticsResponse,
    StationCreate,
    StationHasDataError,
    StationResponse,
    StationUpdate,
    SummaryResponse,
    TemplateResponse,
    UploadPreviewResponse,
    UploadResponse,
)

logger = logging.getLogger("research_agent.monitoring_api")

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"

# ============================================================
# 站点管理
# ============================================================

@router.get("/stations", response_model=list[StationResponse])
async def list_stations(
    type: Optional[str] = Query(None, alias="type", description="数据类型过滤"),
    db: AsyncSession = Depends(get_monitoring_session),
):
    """列出监测站点"""
    return await service_list_stations(db, station_type=type)


@router.get("/stations/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: str,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """查询单个站点"""
    s = await service_get_station(db, station_id)
    if not s:
        raise HTTPException(status_code=404, detail="站点不存在")
    return s


@router.post("/stations", response_model=StationResponse, status_code=201)
async def create_station(
    body: StationCreate,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """创建新站点"""
    # Check code uniqueness
    existing = await get_station_by_code(db, body.station_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"站点编码 {body.station_code} 已存在")
    return await service_create_station(db, body.model_dump())


@router.put("/stations/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: str,
    body: StationUpdate,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """更新站点信息"""
    s = await service_update_station(db, station_id, body.model_dump(exclude_none=True))
    if not s:
        raise HTTPException(status_code=404, detail="站点不存在")
    return s


@router.delete("/stations/{station_id}")
async def delete_station(
    station_id: str,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """删除站点（有数据时返回 409）"""
    result = await service_delete_station(db, station_id)
    if not result.get("success"):
        if result.get("code") == "STATION_HAS_DATA":
            raise HTTPException(status_code=409, detail=StationHasDataError(**result).model_dump())
        elif result.get("code") == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="站点不存在")
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


# ============================================================
# 数据查询
# ============================================================

@router.get("/data/{data_type}", response_model=DataQueryResponse)
async def query_data(
    data_type: str,
    station_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_monitoring_session),
):
    """查询监测测量数据"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}，可选: {', '.join(DATA_TYPES)}")

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    result = await service_query_measurements(
        db, data_type, station_id=station_id, start=start_dt, end=end_dt, limit=limit, offset=offset,
    )
    return result


@router.get("/data/{data_type}/summary", response_model=SummaryResponse)
async def data_summary(
    data_type: str,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """获取某类数据的全局概览"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")
    return await service_get_summary(db, data_type)


@router.get("/data/{data_type}/latest", response_model=LatestResponse)
async def data_latest(
    data_type: str,
    db: AsyncSession = Depends(get_monitoring_session),
):
    """获取各站最新数据"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")
    return await service_get_latest(db, data_type)


@router.get("/data/{data_type}/statistics", response_model=StatisticsResponse)
async def data_statistics(
    data_type: str,
    station_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_monitoring_session),
):
    """获取统计数据"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    return await service_get_statistics(db, data_type, station_id=station_id, start=start_dt, end=end_dt)


# ============================================================
# 数据上传
# ============================================================

@router.post("/upload", response_model=UploadResponse)
async def upload_data(
    file: UploadFile = File(..., description="CSV/XLSX 数据文件"),
    data_type: str = Form(..., description="数据类型: groundwater/rainfall/pore_pressure/gnss/insar"),
    station_code: Optional[str] = Form(None, description="当文件不含 station_code 列时统一使用此值"),
    create_stations: bool = Form(True, description="是否自动创建站点"),
):
    """上传 CSV/XLSX 文件并导入监测数据库"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    # Save file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "data.csv").suffix or ".csv"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / unique_name

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    save_path.write_bytes(content)

    # Import
    result = await import_from_file(
        file_path=save_path,
        data_type=data_type,
        station_code_override=station_code,
        create_stations=create_stations,
    )

    result["file_id"] = unique_name
    return result


@router.post("/upload/preview", response_model=UploadPreviewResponse)
async def preview_upload(
    file: UploadFile = File(..., description="CSV/XLSX 数据文件"),
    data_type: str = Form(..., description="数据类型"),
):
    """预览上传文件（校验列名、解析结果，不入库）"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    # Save temp file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "data.csv").suffix or ".csv"
    temp_name = f"_preview_{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / temp_name

    content = await file.read()
    save_path.write_bytes(content)

    try:
        result = preview_import(save_path, data_type)
        return result
    finally:
        # Cleanup temp file
        if save_path.exists():
            save_path.unlink()


@router.get("/upload/template/{data_type}")
async def download_template(data_type: str):
    """下载导入模板 CSV"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    info = get_template_columns(data_type)
    columns = [c["name"] for c in info["columns"]]
    example = info.get("example_row", {})

    # Build CSV content
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerow([example.get(c, "") for c in columns])

    filename = f"{data_type}_template.csv"
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/upload/template/{data_type}/info", response_model=TemplateResponse)
async def get_template_info(data_type: str):
    """获取导入模板列信息"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")
    return get_template_columns(data_type)


# ============================================================
# 数据删除
# ============================================================

@router.delete("/data/{data_type}", response_model=DeleteResponse)
async def delete_data(
    data_type: str,
    station_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    before: Optional[str] = Query(None),
    dry_run: bool = Query(True, description="预览模式（不删除）"),
    db: AsyncSession = Depends(get_monitoring_session),
):
    """按条件删除监测数据（默认 dry_run 只统计不删除）"""
    if data_type not in DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    before_dt = datetime.fromisoformat(before) if before else None

    result = await service_delete_measurements(
        db, data_type,
        station_id=station_id,
        start=start_dt,
        end=end_dt,
        before=before_dt,
        dry_run=dry_run,
    )
    return result


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_data(
    body: CleanupRequest,
):
    """批量清理过期数据"""
    before_dt = datetime.fromisoformat(body.before)
    result = await service_batch_cleanup(
        data_types=body.data_types,
        before=before_dt,
        station_ids=body.station_ids,
        dry_run=body.dry_run,
    )
    return result
