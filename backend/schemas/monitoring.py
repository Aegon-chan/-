"""监测数据 API 的 Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 站点
# ============================================================

class StationCreate(BaseModel):
    station_code: str = Field(..., description="站点编码，如 GW-01")
    station_name: str = Field("", description="站点名称")
    station_type: str = Field(..., description="数据类型: groundwater/rainfall/pore_pressure/gnss/insar")
    longitude: Optional[float] = Field(None, description="经度")
    latitude: Optional[float] = Field(None, description="纬度")
    altitude: Optional[float] = Field(None, description="高程 (m)")
    description: str = Field("", description="位置描述")
    status: str = Field("active", description="状态: active/inactive")


class StationUpdate(BaseModel):
    station_name: Optional[str] = Field(None)
    longitude: Optional[float] = Field(None)
    latitude: Optional[float] = Field(None)
    altitude: Optional[float] = Field(None)
    description: Optional[str] = Field(None)
    status: Optional[str] = Field(None)


class StationResponse(BaseModel):
    id: int
    station_code: str
    station_name: str
    station_type: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    altitude: Optional[float] = None
    description: str = ""
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ============================================================
# 数据查询
# ============================================================

class DataQueryParams(BaseModel):
    station_id: Optional[int] = Field(None, description="站点 ID")
    start: Optional[str] = Field(None, description="起始时间 (ISO 格式)")
    end: Optional[str] = Field(None, description="结束时间 (ISO 格式)")
    limit: int = Field(100, description="返回条数上限", ge=1, le=10000)
    offset: int = Field(0, description="偏移量")


class DataPoint(BaseModel):
    id: int
    station_id: int
    measurement_time: str
    values: dict[str, Any] = Field(default_factory=dict, description="各字段的值")


class DataQueryResponse(BaseModel):
    success: bool = True
    data_type: str
    total: int = 0
    returned: int = 0
    offset: int = 0
    limit: int = 100
    records: list[DataPoint] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    success: bool = True
    data_type: str
    total_records: int = 0
    station_count: int = 0
    time_range: dict[str, Optional[str]] = Field(default_factory=lambda: {"start": None, "end": None})
    stations: list[dict[str, Any]] = Field(default_factory=list)


class LatestResponse(BaseModel):
    success: bool = True
    data_type: str
    records: list[dict[str, Any]] = Field(default_factory=list)


class StatisticsResponse(BaseModel):
    success: bool = True
    data_type: str
    station_id: Optional[int] = None
    count: int = 0
    mean: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    std: Optional[float] = None
    time_range: dict[str, Optional[str]] = Field(default_factory=lambda: {"start": None, "end": None})


# ============================================================
# 数据上传
# ============================================================

class UploadResponse(BaseModel):
    success: bool = True
    file_id: str = ""
    data_type: str = ""
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    stations_created: list[str] = Field(default_factory=list)
    stations_existing: list[str] = Field(default_factory=list)
    time_range: dict[str, Optional[str]] = Field(default_factory=lambda: {"start": None, "end": None})
    errors: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class UploadPreviewResponse(BaseModel):
    success: bool = True
    data_type: str = ""
    total_rows: int = 0
    column_mapping: dict[str, str] = Field(default_factory=dict)
    missing_required: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    estimated_stations: list[str] = Field(default_factory=list)
    time_range: dict[str, Optional[str]] = Field(default_factory=lambda: {"start": None, "end": None})
    potential_issues: list[str] = Field(default_factory=list)
    import_preview: dict[str, Any] = Field(default_factory=dict)


class ColumnInfo(BaseModel):
    name: str = ""
    required: bool = False
    description: str = ""


class TemplateResponse(BaseModel):
    data_type: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)
    example_row: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# 数据删除
# ============================================================

class DeleteCondition(BaseModel):
    station_id: Optional[int] = Field(None, description="站点 ID")
    start: Optional[str] = Field(None, description="起始时间")
    end: Optional[str] = Field(None, description="结束时间")
    before: Optional[str] = Field(None, description="删除此时间之前的数据")


class DeleteResponse(BaseModel):
    success: bool = True
    dry_run: bool = True
    deleted_count: int = 0
    matched_count: int = 0
    condition: dict[str, Any] = Field(default_factory=dict)
    data_type: Optional[str] = None
    message: str = ""


class CleanupRequest(BaseModel):
    data_types: list[str] = Field(default_factory=list, description="要清理的数据类型列表，空列表表示全部")
    before: str = Field(..., description="删除此时间之前的数据 (ISO 格式)")
    station_ids: Optional[list[str]] = Field(None, description="指定站点列表，null 表示全部")
    dry_run: bool = Field(True, description="预览模式")


class CleanupResponse(BaseModel):
    success: bool = True
    dry_run: bool = True
    results: dict[str, Any] = Field(default_factory=dict, description="每种数据类型的删除结果")
    total_deleted: int = 0
    message: str = ""


# ============================================================
# 通用
# ============================================================

class StationHasDataError(BaseModel):
    success: bool = False
    code: str = "STATION_HAS_DATA"
    message: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
