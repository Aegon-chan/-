"""监测数据查询服务层。

封装对 monitoring_data.db 的所有查询逻辑，供 API 和 Agent 调用。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.monitoring_models import (
    DATA_TYPE_LABEL_MAP,
    MonitoringStation,
    get_model_for_data_type,
    get_time_column_name,
)
from backend.db.monitoring_session import (
    AsyncSessionLocal,
)

logger = logging.getLogger("research_agent.monitoring_service")

DATA_TYPES = ["groundwater", "rainfall", "pore_pressure", "gnss", "insar"]


# ============================================================
# 站点管理
# ============================================================

async def list_stations(
    db: AsyncSession,
    station_type: Optional[str] = None,
) -> list[dict]:
    """列出监测站点，可按类型过滤"""
    q = select(MonitoringStation).order_by(MonitoringStation.station_code)
    if station_type:
        q = q.where(MonitoringStation.station_type == station_type)
    result = await db.execute(q)
    stations = result.scalars().all()
    return [_station_to_dict(s) for s in stations]


async def get_station(db: AsyncSession, station_id: str) -> Optional[dict]:
    """按 ID 查询站点"""
    q = select(MonitoringStation).where(MonitoringStation.id == station_id)
    result = await db.execute(q)
    s = result.scalar_one_or_none()
    return _station_to_dict(s) if s else None


async def get_station_by_code(db: AsyncSession, code: str) -> Optional[dict]:
    """按编码查询站点"""
    q = select(MonitoringStation).where(MonitoringStation.station_code == code)
    result = await db.execute(q)
    s = result.scalar_one_or_none()
    return _station_to_dict(s) if s else None


async def create_station(db: AsyncSession, data: dict) -> dict:
    """创建新站点"""
    s = MonitoringStation(**data)
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return _station_to_dict(s)


async def update_station(db: AsyncSession, station_id: str, data: dict) -> Optional[dict]:
    """更新站点信息"""
    q = select(MonitoringStation).where(MonitoringStation.id == station_id)
    result = await db.execute(q)
    s = result.scalar_one_or_none()
    if not s:
        return None
    for key, value in data.items():
        if value is not None and hasattr(s, key):
            setattr(s, key, value)
    await db.flush()
    await db.refresh(s)
    return _station_to_dict(s)


async def delete_station(db: AsyncSession, station_id: str) -> dict:
    """删除站点（如有数据则阻止）"""
    q = select(MonitoringStation).where(MonitoringStation.id == station_id)
    result = await db.execute(q)
    s = result.scalar_one_or_none()
    if not s:
        return {"success": False, "code": "NOT_FOUND", "message": "站点不存在"}

    # 检查是否有关联数据
    data_counts = await count_station_data_by_type(db, station_id)
    has_data = any(v > 0 for v in data_counts.values())
    if has_data:
        detail = {"station_code": s.station_code, "station_name": s.station_name, "data_counts": data_counts}
        return {
            "success": False,
            "code": "STATION_HAS_DATA",
            "message": f"站点 {s.station_code} 仍有数据，无法删除",
            "detail": detail,
        }

    await db.delete(s)
    await db.flush()
    return {"success": True, "deleted": True}


async def count_station_data_by_type(db: AsyncSession, station_id: str) -> dict[str, int]:
    """统计某站点各类型数据量"""
    counts = {}
    for dt in DATA_TYPES:
        model = get_model_for_data_type(dt)
        if model:
            q = select(func.count(model.id)).where(model.station_id == station_id)
            result = await db.execute(q)
            counts[dt] = result.scalar() or 0
    return counts


# ============================================================
# 数据查询
# ============================================================

async def query_measurements(
    db: AsyncSession,
    data_type: str,
    station_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """查询测量数据"""
    model = get_model_for_data_type(data_type)
    if not model:
        return {"success": False, "error": f"不支持的数据类型: {data_type}"}

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    # Build query
    conditions = []
    if station_id:
        conditions.append(model.station_id == station_id)
    if start:
        conditions.append(time_col >= start)
    if end:
        conditions.append(time_col <= end)

    # Count total
    count_q = select(func.count(model.id))
    if conditions:
        count_q = count_q.where(*conditions)
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch records
    q = select(model).order_by(time_col.desc())
    if conditions:
        q = q.where(*conditions)
    q = q.offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    records = []
    for r in rows:
        r_dict = _measurement_to_dict(r, model, time_col_name)
        records.append(r_dict)

    return {
        "success": True,
        "data_type": data_type,
        "total": total,
        "returned": len(records),
        "offset": offset,
        "limit": limit,
        "records": records,
    }


async def get_summary(db: AsyncSession, data_type: str) -> dict:
    """获取某类数据的全局概览"""
    model = get_model_for_data_type(data_type)
    if not model:
        return {"success": False, "error": f"不支持的数据类型: {data_type}"}

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    # Total records
    count_q = select(func.count(model.id))
    total = (await db.execute(count_q)).scalar() or 0

    # Time range
    time_q = select(func.min(time_col), func.max(time_col))
    time_result = await db.execute(time_q)
    min_time, max_time = time_result.one()

    # Stations with data
    station_q = select(model.station_id).distinct()
    station_result = await db.execute(station_q)
    station_ids = [r[0] for r in station_result.fetchall()]

    # Get station info
    stations_info = []
    if station_ids:
        sq = select(MonitoringStation).where(MonitoringStation.id.in_(station_ids))
        s_result = await db.execute(sq)
        for st in s_result.scalars().all():
            stations_info.append({
                "id": st.id,
                "station_code": st.station_code,
                "station_name": st.station_name,
            })

    return {
        "success": True,
        "data_type": data_type,
        "total_records": total,
        "station_count": len(stations_info),
        "time_range": {
            "start": min_time.isoformat() if min_time else None,
            "end": max_time.isoformat() if max_time else None,
        },
        "stations": stations_info,
    }


async def get_latest(db: AsyncSession, data_type: str) -> dict:
    """获取各站最新数据"""
    model = get_model_for_data_type(data_type)
    if not model:
        return {"success": False, "error": f"不支持的数据类型: {data_type}"}

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    # Get distinct station_ids
    sid_q = select(model.station_id).distinct()
    sid_result = await db.execute(sid_q)
    station_ids = [r[0] for r in sid_result.fetchall()]

    records = []
    for sid in station_ids:
        q = (select(model)
             .where(model.station_id == sid)
             .order_by(time_col.desc())
             .limit(1))
        r = (await db.execute(q)).scalar_one_or_none()
        if r:
            r_dict = _measurement_to_dict(r, model, time_col_name)
            # Add station info
            st = await get_station(db, sid)
            if st:
                r_dict["station_code"] = st["station_code"]
                r_dict["station_name"] = st["station_name"]
            records.append(r_dict)

    return {"success": True, "data_type": data_type, "records": records}


async def get_statistics(
    db: AsyncSession,
    data_type: str,
    station_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> dict:
    """获取统计信息（均值/极值/标准差）"""
    model = get_model_for_data_type(data_type)
    if not model:
        return {"success": False, "error": f"不支持的数据类型: {data_type}"}

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    # Find the numeric value column
    value_col_name = _get_value_column(data_type)
    if not value_col_name:
        return {"success": False, "error": "无法确定数值列"}
    value_col = getattr(model, value_col_name)

    conditions = []
    if station_id:
        conditions.append(model.station_id == station_id)
    if start:
        conditions.append(time_col >= start)
    if end:
        conditions.append(time_col <= end)

    # Count
    count_q = select(func.count(model.id))
    if conditions:
        count_q = count_q.where(*conditions)
    count = (await db.execute(count_q)).scalar() or 0

    if count == 0:
        return {"success": True, "data_type": data_type, "count": 0}

    # Aggregate
    agg_q = select(
        func.avg(value_col),
        func.min(value_col),
        func.max(value_col),
        # SQLite does not support stddev(), compute manually
        func.min(time_col),
        func.max(time_col),
    )
    if conditions:
        agg_q = agg_q.where(*conditions)
    agg_result = await db.execute(agg_q)
    row = agg_result.one()

    return {
        "success": True,
        "data_type": data_type,
        "station_id": station_id,
        "count": count,
        "mean": round(float(row[0]), 4) if row[0] is not None else None,
        "min": round(float(row[1]), 4) if row[1] is not None else None,
        "max": round(float(row[2]), 4) if row[2] is not None else None,
        "std": None,  # SQLite does not support stddev(), computed on request
        "time_range": {
            "start": row[3].isoformat() if row[3] else None,
            "end": row[4].isoformat() if row[4] else None,
        },
    }


# ============================================================
# 数据删除
# ============================================================

async def delete_measurements(
    db: AsyncSession,
    data_type: str,
    station_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    before: Optional[datetime] = None,
    dry_run: bool = True,
) -> dict:
    """按条件删除测量数据，默认 dry_run 只统计不删除"""
    model = get_model_for_data_type(data_type)
    if not model:
        return {"success": False, "error": f"不支持的数据类型: {data_type}"}

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    conditions = []
    if station_id:
        conditions.append(model.station_id == station_id)
    if start:
        conditions.append(time_col >= start)
    if end:
        conditions.append(time_col <= end)
    if before:
        conditions.append(time_col < before)

    if not conditions:
        return {"success": False, "error": "请至少提供一个筛选条件"}

    # Count matching records
    count_q = select(func.count(model.id)).where(*conditions)
    matched = (await db.execute(count_q)).scalar() or 0

    condition_info = {
        "data_type": data_type,
        "station_id": station_id,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "before": before.isoformat() if before else None,
    }

    if dry_run or matched == 0:
        return {
            "success": True,
            "dry_run": dry_run,
            "matched_count": matched,
            "deleted_count": 0,
            "condition": condition_info,
            "data_type": data_type,
            "message": f"匹配 {matched} 条记录。{'设置 dry_run=false 执行删除' if dry_run else ''}",
        }

    # Execute delete
    delete_q = sa_delete(model).where(*conditions)
    result = await db.execute(delete_q)
    deleted = result.rowcount

    return {
        "success": True,
        "dry_run": False,
        "matched_count": matched,
        "deleted_count": deleted,
        "condition": condition_info,
        "data_type": data_type,
        "message": f"已删除 {deleted} 条{_data_type_label(data_type)}数据",
    }


async def batch_cleanup(
    data_types: list[str],
    before: datetime,
    station_ids: Optional[list[str]] = None,
    dry_run: bool = True,
) -> dict:
    """批量清理过期数据"""
    if not data_types:
        data_types = DATA_TYPES.copy()

    results = {}
    total_deleted = 0

    async with AsyncSessionLocal() as db:
        try:
            for dt in data_types:
                result = await delete_measurements(
                    db=db,
                    data_type=dt,
                    before=before,
                    station_id=None,
                    dry_run=dry_run,
                )
                results[dt] = result
                if not dry_run and result.get("success"):
                    total_deleted += result.get("deleted_count", 0)
                elif dry_run:
                    total_deleted += result.get("matched_count", 0)

            if not dry_run and total_deleted > 0:
                await db.commit()

            return {
                "success": True,
                "dry_run": dry_run,
                "results": results,
                "total_deleted": total_deleted,
                "message": f"{'预览' if dry_run else '完成'}：共匹配 {total_deleted} 条记录",
            }
        except Exception as e:
            await db.rollback()
            logger.exception("Batch cleanup failed")
            return {"success": False, "error": str(e)}


# ============================================================
# 供 NL2Query 使用（获取 DataFrame）
# ============================================================

async def get_all_data_for_analysis(
    data_type: str,
    station_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Optional["pd.DataFrame"]:  # noqa: F821
    """获取监测数据为 pandas DataFrame，供 NL2Query sandbox 使用"""
    import pandas as pd

    model = get_model_for_data_type(data_type)
    if not model:
        return None

    time_col_name = get_time_column_name(data_type)
    time_col = getattr(model, time_col_name)

    conditions = []
    if station_id:
        conditions.append(model.station_id == station_id)
    if start:
        conditions.append(time_col >= start)
    if end:
        conditions.append(time_col <= end)

    q = select(model).order_by(time_col)
    if conditions:
        q = q.where(*conditions)

    async with AsyncSessionLocal() as db:
        result = await db.execute(q)
        rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        r_dict = {"id": r.id, "station_id": r.station_id}
        r_dict[time_col_name] = getattr(r, time_col_name)
        for col in model.__table__.columns.keys():
            if col not in ("id", "station_id", "created_at", time_col_name):
                val = getattr(r, col)
                if val is not None:
                    r_dict[col] = val
        records.append(r_dict)

    df = pd.DataFrame(records)
    if time_col_name in df.columns:
        df[time_col_name] = pd.to_datetime(df[time_col_name])
    return df


# ============================================================
# 内部工具函数
# ============================================================

def _station_to_dict(s: MonitoringStation) -> dict:
    return {
        "id": s.id,
        "station_code": s.station_code,
        "station_name": s.station_name,
        "station_type": s.station_type,
        "longitude": s.longitude,
        "latitude": s.latitude,
        "altitude": s.altitude,
        "description": s.description,
        "status": s.status,
    }


def _measurement_to_dict(r, model, time_col_name: str) -> dict:
    """将 ORM 对象转为字典"""
    r_dict = {"id": r.id, "station_id": r.station_id}
    time_val = getattr(r, time_col_name)
    r_dict["measurement_time"] = time_val.isoformat() if time_val else None
    values = {}
    for col in model.__table__.columns.keys():
        if col not in ("id", "station_id", "created_at", time_col_name):
            val = getattr(r, col)
            if val is not None:
                values[col] = val
    r_dict["values"] = values
    return r_dict


VALUE_COLUMNS = {
    "groundwater": "water_level",
    "rainfall": "rainfall_amount",
    "pore_pressure": "pressure_value",
    "gnss": "dx",
    "insar": "los_displacement",
}


def _get_value_column(data_type: str) -> Optional[str]:
    return VALUE_COLUMNS.get(data_type)


def _data_type_label(data_type: str) -> str:
    return DATA_TYPE_LABEL_MAP.get(data_type, data_type)
