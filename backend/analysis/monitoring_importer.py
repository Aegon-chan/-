"""监测数据导入解析器。

支持 CSV/XLSX 解析、列名标准化（中英文别名匹配）、
数据校验、自动建站、批量入库。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from backend.db.monitoring_session import AsyncSessionLocal
from backend.db.monitoring_models import (
    DATA_TYPE_LABEL_MAP,
    ImportBatch,
    MonitoringStation,
    GroundwaterMeasurement,
    RainfallMeasurement,
    PorePressureMeasurement,
    GnssMeasurement,
    InSARMeasurement,
    get_model_for_data_type,
    get_time_column_name,
)

logger = logging.getLogger("research_agent.monitoring_importer")

BATCH_SIZE = 500

# ============================================================
# 列映射定义
# ============================================================

COLUMN_SCHEMAS = {
    "groundwater": {
        "required": ["station_code", "measurement_time", "water_level"],
        "optional": ["water_depth", "temperature", "conductivity"],
        "aliases": {
            "测站编号": "station_code", "站点编号": "station_code",
            "站点编码": "station_code", "站号": "station_code",
            "station": "station_code", "code": "station_code",
            "监测时间": "measurement_time", "观测时间": "measurement_time",
            "时间": "measurement_time", "日期": "measurement_time",
            "time": "measurement_time", "date": "measurement_time",
            "datetime": "measurement_time", "timestamp": "measurement_time",
            "水位": "water_level", "地下水位": "water_level",
            "level": "water_level", "waterlevel": "water_level",
            "埋深": "water_depth", "水深": "water_depth",
            "depth": "water_depth", "waterdepth": "water_depth",
            "水温": "temperature", "温度": "temperature",
            "temp": "temperature",
            "电导率": "conductivity", "cond": "conductivity",
        },
    },
    "rainfall": {
        "required": ["station_code", "measurement_time", "rainfall_amount"],
        "optional": ["intensity", "duration_min"],
        "aliases": {
            "测站编号": "station_code", "站点编号": "station_code",
            "站点编码": "station_code", "站号": "station_code",
            "station": "station_code", "code": "station_code",
            "监测时间": "measurement_time", "观测时间": "measurement_time",
            "时间": "measurement_time", "日期": "measurement_time",
            "time": "measurement_time", "date": "measurement_time",
            "降雨量": "rainfall_amount", "降雨": "rainfall_amount",
            "降水量": "rainfall_amount", "降水": "rainfall_amount",
            "雨量": "rainfall_amount", "rain": "rainfall_amount",
            "rainfall": "rainfall_amount", "amount": "rainfall_amount",
            "强度": "intensity", "降雨强度": "intensity",
            "rain intensity": "intensity",
            "持续时间": "duration_min", "时长": "duration_min",
            "duration": "duration_min", "minutes": "duration_min",
        },
    },
    "pore_pressure": {
        "required": ["station_code", "measurement_time", "pressure_value"],
        "optional": ["temperature"],
        "aliases": {
            "测站编号": "station_code", "站点编号": "station_code",
            "站点编码": "station_code", "站号": "station_code",
            "station": "station_code", "code": "station_code",
            "监测时间": "measurement_time", "观测时间": "measurement_time",
            "时间": "measurement_time", "日期": "measurement_time",
            "time": "measurement_time", "date": "measurement_time",
            "孔隙水压力": "pressure_value", "孔压": "pressure_value",
            "孔隙压力": "pressure_value", "压力": "pressure_value",
            "pressure": "pressure_value", "pore pressure": "pressure_value",
            "水温": "temperature", "温度": "temperature",
            "temp": "temperature",
        },
    },
    "gnss": {
        "required": ["station_code", "measurement_time", "dx", "dy", "dz"],
        "optional": ["hdop", "vdop"],
        "aliases": {
            "测站编号": "station_code", "站点编号": "station_code",
            "站点编码": "station_code", "站号": "station_code",
            "station": "station_code", "code": "station_code",
            "监测时间": "measurement_time", "观测时间": "measurement_time",
            "时间": "measurement_time", "日期": "measurement_time",
            "time": "measurement_time", "date": "measurement_time",
            "东西向位移": "dx", "东向位移": "dx",
            "easting": "dx", "east": "dx",
            "南北向位移": "dy", "北向位移": "dy",
            "northing": "dy", "north": "dy",
            "垂直位移": "dz", "垂向位移": "dz",
            "vertical": "dz", "up": "dz",
            "水平精度": "hdop", "HDOP": "hdop",
            "垂直精度": "vdop", "VDOP": "vdop",
        },
    },
    "insar": {
        "required": ["station_code", "acquisition_time", "los_displacement"],
        "optional": ["coherence", "incidence_angle", "track_number"],
        "aliases": {
            "测站编号": "station_code", "站点编号": "station_code",
            "站点编码": "station_code", "站号": "station_code",
            "station": "station_code", "code": "station_code",
            "获取时间": "acquisition_time", "影像时间": "acquisition_time",
            "时间": "acquisition_time", "日期": "acquisition_time",
            "acquisition": "acquisition_time", "date": "acquisition_time",
            "视线向形变": "los_displacement", "LOS形变": "los_displacement",
            "形变量": "los_displacement", "los": "los_displacement",
            "displacement": "los_displacement",
            "相干性": "coherence", "coherence": "coherence",
            "入射角": "incidence_angle", "incidence": "incidence_angle",
            "轨道编号": "track_number", "轨道": "track_number",
            "track": "track_number",
        },
    },
}

STATION_TYPES = {
    "groundwater": "groundwater",
    "rainfall": "rainfall",
    "pore_pressure": "pore_pressure",
    "gnss": "gnss",
    "insar": "insar",
}

MODEL_MAP = {
    "groundwater": GroundwaterMeasurement,
    "rainfall": RainfallMeasurement,
    "pore_pressure": PorePressureMeasurement,
    "gnss": GnssMeasurement,
    "insar": InSARMeasurement,
}

TIME_FMT_CANDIDATES = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y年%m月%d日 %H:%M",
    "%Y年%m月%d日",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
]


# ============================================================
# 核心导入函数
# ============================================================

class ImportResult:
    """导入结果"""
    def __init__(self):
        self.total_rows = 0
        self.imported = 0
        self.skipped = 0
        self.stations_created: list[str] = []
        self.stations_existing: list[str] = []
        self.errors: list[dict] = []
        self.time_range: dict = {"start": None, "end": None}

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "imported": self.imported,
            "skipped": self.skipped,
            "stations_created": self.stations_created,
            "stations_existing": self.stations_existing,
            "time_range": self.time_range,
            "errors": self.errors[:50],  # 最多返回 50 条错误
        }


def normalize_columns(df: pd.DataFrame, data_type: str) -> tuple[list[str], dict[str, str], list[str]]:
    """标准化列名：中文/变体 → 标准字段名。

    Returns:
        (matched_columns, mapping, missing_required)
    """
    schema = COLUMN_SCHEMAS.get(data_type)
    if not schema:
        return [], {}, list(schema["required"]) if schema else ["data_type"]

    aliases = schema["aliases"]
    required = schema["required"]

    mapping = {}
    matched = []
    for col in df.columns:
        col_clean = col.strip().lower()
        if col_clean in aliases:
            std_name = aliases[col_clean]
            mapping[col] = std_name
            matched.append(std_name)
        elif col_clean in required or col_clean in schema.get("optional", []):
            # Direct match (English column name already normalized to lower)
            # Find the exact required name
            for r in required + schema.get("optional", []):
                if col_clean == r.lower():
                    mapping[col] = r
                    matched.append(r)
                    break

    # Find missing required columns
    missing_required = [r for r in required if r not in matched]

    return matched, mapping, missing_required


def parse_time(value) -> Optional[datetime]:
    """尝试多种格式解析时间字符串"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, (int, float)):
        # Excel serial date
        from datetime import timedelta
        try:
            base = datetime(1899, 12, 30)
            return base + timedelta(days=float(value))
        except Exception:
            pass
    s = str(value).strip()
    if not s:
        return None
    for fmt in TIME_FMT_CANDIDATES:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Try pandas parse
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None


def to_float(value) -> Optional[float]:
    """安全转浮点"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_int(value) -> Optional[int]:
    """安全转整数"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


async def import_from_df(
    df: pd.DataFrame,
    data_type: str,
    station_code_override: Optional[str] = None,
    create_stations: bool = True,
) -> dict:
    """从 DataFrame 导入监测数据

    Args:
        df: 数据 DataFrame
        data_type: 数据类型
        station_code_override: 如果文件不含 station_code，统一使用此值
        create_stations: 是否自动创建不存在的站点

    Returns:
        导入结果 dict
    """
    result = ImportResult()
    result.total_rows = len(df)

    # 1. Normalize column names
    matched_cols, col_mapping, missing_required = normalize_columns(df, data_type)

    if missing_required:
        return {
            "success": False,
            "total_rows": len(df),
            "imported": 0,
            "skipped": len(df),
            "stations_created": [],
            "stations_existing": [],
            "time_range": {"start": None, "end": None},
            "errors": [{"row": 0, "reason": f"缺少必填列: {', '.join(missing_required)}。可用列: {list(df.columns)}"}],
            "message": f"缺少必填列: {', '.join(missing_required)}",
        }

    # 2. Rename columns
    df_std = df.rename(columns=col_mapping)

    # 3. Handle station_code
    if "station_code" not in df_std.columns:
        if station_code_override:
            df_std["station_code"] = station_code_override
        else:
            return {"success": False, "total_rows": len(df), "imported": 0, "skipped": len(df),
                    "errors": [{"row": 0, "reason": "缺少 station_code 列且未提供 station_code 参数"}],
                    "message": "缺少 station_code"}

    # 4. Identify time column
    time_col_name = get_time_column_name(data_type)

    # 5. Parse and validate rows
    model_class = MODEL_MAP.get(data_type)
    if not model_class:
        return {"success": False, "message": f"不支持的数据类型: {data_type}"}

    schema = COLUMN_SCHEMAS.get(data_type, {})
    all_cols = schema["required"] + schema["optional"]

    records = []
    seen_stations = set()
    station_cache = {}

    for idx, row in df_std.iterrows():
        row_num = idx + 2  # 1-indexed with header
        row_errors = []

        # Parse station_code
        sc = str(row.get("station_code", "")).strip()
        if not sc:
            result.errors.append({"row": row_num, "reason": "station_code 为空"})
            result.skipped += 1
            continue
        seen_stations.add(sc)

        # Parse time
        raw_time = row.get(time_col_name)
        parsed_time = parse_time(raw_time)
        if not parsed_time:
            result.errors.append({"row": row_num, "reason": f"{time_col_name} 无法解析: {raw_time}"})
            result.skipped += 1
            continue

        # Build record
        record = {
            "station_code": sc,
            time_col_name: parsed_time,
        }

        # Parse value columns
        for col in all_cols:
            if col in ("station_code", "measurement_time", "acquisition_time"):
                continue
            if col in row and pd.notna(row[col]):
                if col == "duration_min":
                    val = to_int(row[col])
                else:
                    val = to_float(row[col])
                if val is not None:
                    record[col] = val

        # Validate required values
        required_value_cols = [c for c in schema["required"] if c not in ("station_code", "measurement_time", "acquisition_time")]
        for rvc in required_value_cols:
            if rvc not in record or record[rvc] is None:
                result.errors.append({"row": row_num, "reason": f"必填字段 {rvc} 为空或无效"})
                result.skipped += 1
                record = None
                break

        if record is not None:
            records.append(record)

    if not records:
        return {
            "success": False,
            "total_rows": len(df),
            "imported": 0,
            "skipped": len(df),
            "stations_created": [],
            "stations_existing": [],
            "errors": result.errors[:50],
            "message": "所有行均无效",
        }

    # 6. Store stations and data in DB
    async with AsyncSessionLocal() as db:
        try:
            # Create batch record
            import uuid
            batch_id = str(uuid.uuid4())
            batch_label = ""
            batch = ImportBatch(
                id=batch_id,
                data_type=data_type,
                file_name="",
                batch_label=batch_label,
                total_rows=len(records),
                imported_rows=0,
                skipped_rows=result.skipped,
            )
            db.add(batch)
            await db.flush()
            result.batch_id = batch_id

            # Resolve stations
            station_id_map = {}
            for sc in seen_stations:
                from sqlalchemy import select
                q = select(MonitoringStation).where(MonitoringStation.station_code == sc)
                existing = (await db.execute(q)).scalar_one_or_none()
                if existing:
                    station_id_map[sc] = existing.id
                    result.stations_existing.append(sc)
                elif create_stations:
                    station = MonitoringStation(
                        station_code=sc,
                        station_name=f"{sc} ({DATA_TYPE_LABEL_MAP.get(data_type, data_type)})",
                        station_type=STATION_TYPES.get(data_type, data_type),
                        description=f"从 {data_type} 数据导入自动创建",
                    )
                    db.add(station)
                    await db.flush()
                    await db.refresh(station)
                    station_id_map[sc] = station.id
                    result.stations_created.append(sc)
                else:
                    continue

            if not station_id_map:
                return {
                    "success": False,
                    "total_rows": len(df),
                    "imported": 0,
                    "skipped": len(records),
                    "stations_created": [],
                    "stations_existing": list(seen_stations),
                    "errors": [{"row": 0, "reason": "未找到站点且 create_stations=False"}],
                    "message": "未找到站点",
                }

            # Prepare ORM objects
            objs = []
            time_min = None
            time_max = None
            for rec in records:
                sc = rec.pop("station_code")
                sid = station_id_map.get(sc)
                if not sid:
                    continue
                obj = model_class(station_id=sid, **rec)
                objs.append(obj)

                # Track time range
                t = rec.get(time_col_name)
                if t:
                    if time_min is None or t < time_min:
                        time_min = t
                    if time_max is None or t > time_max:
                        time_max = t

            # Batch insert
            for i in range(0, len(objs), BATCH_SIZE):
                chunk = objs[i:i + BATCH_SIZE]
                db.add_all(chunk)
                await db.flush()

            await db.commit()

            result.imported = len(objs)
            # Update batch record
            batch.imported_rows = result.imported
            if time_min and time_max:
                batch.time_range_start = time_min
                batch.time_range_end = time_max
            result.time_range = {
                "start": time_min.isoformat() if time_min else None,
                "end": time_max.isoformat() if time_max else None,
            }

            return {
                "success": True,
                "batch_id": batch_id,
                "total_rows": result.total_rows,
                "imported": result.imported,
                "skipped": result.skipped,
                "stations_created": result.stations_created,
                "stations_existing": result.stations_existing,
                "time_range": result.time_range,
                "errors": result.errors[:50],
                "message": f"成功导入 {result.imported} 条{_label(data_type)}数据，跳过 {result.skipped} 行",
            }

        except Exception as e:
            await db.rollback()
            logger.exception("Import failed")
            return {
                "success": False,
                "total_rows": len(df),
                "imported": 0,
                "skipped": len(df),
                "stations_created": [],
                "stations_existing": [],
                "errors": [{"row": 0, "reason": f"导入异常: {str(e)}"}],
                "message": f"导入失败: {str(e)}",
            }


async def import_from_file(
    file_path: Path,
    data_type: str,
    station_code_override: Optional[str] = None,
    create_stations: bool = True,
) -> dict:
    """从文件读取并导入监测数据"""
    from backend.analysis.data_loader import read_data_file

    df = read_data_file(file_path)
    if df is None or df.empty:
        return {
            "success": False,
            "total_rows": 0,
            "imported": 0,
            "skipped": 0,
            "stations_created": [],
            "stations_existing": [],
            "errors": [{"row": 0, "reason": "文件为空或无法读取"}],
            "message": "文件为空或无法读取",
        }

    return await import_from_df(df, data_type, station_code_override, create_stations)


def preview_import(
    file_path: Path,
    data_type: str,
) -> dict:
    """预览并校验导入文件（不入库）"""
    from backend.analysis.data_loader import read_data_file

    df = read_data_file(file_path)
    if df is None or df.empty:
        return {
            "success": False,
            "data_type": data_type,
            "total_rows": 0,
            "column_mapping": {},
            "missing_required": [],
            "sample_rows": [],
            "potential_issues": [],
            "import_preview": {"valid_rows": 0, "invalid_rows": 0},
            "message": "文件为空或无法读取",
        }

    # Normalize columns
    matched_cols, col_mapping, missing_required = normalize_columns(df, data_type)

    time_col_name = get_time_column_name(data_type)
    schema = COLUMN_SCHEMAS.get(data_type, {})
    all_cols = schema["required"] + schema["optional"]

    # Preview results
    sample_rows = df.head(5).fillna("").to_dict(orient="records")
    sample_rows_clean = []
    for row in sample_rows:
        clean = {}
        for k, v in row.items():
            clean[k] = str(v)[:50]
        sample_rows_clean.append(clean)

    estimated_stations = set()
    if "station_code" in df.columns:
        for sc in df["station_code"].dropna().unique():
            estimated_stations.add(str(sc))

    # Check potential issues
    issues = []
    if missing_required:
        issues.append(f"缺少必填列: {', '.join(missing_required)}")

    # Check time column
    time_col_orig = None
    for orig, std in col_mapping.items():
        if std == time_col_name:
            time_col_orig = orig
            break
    if time_col_orig and time_col_orig in df.columns:
        non_null_times = df[time_col_orig].dropna()
        bad_times = 0
        for t in non_null_times.head(100):
            if not parse_time(t):
                bad_times += 1
        if bad_times > 5:
            issues.append(f"{time_col_orig} 列有 {bad_times}/{min(100, len(non_null_times))} 个时间值无法解析")

    # Try parsing first 20 rows for validation
    valid_rows = 0
    invalid_rows = 0
    for idx, row in df.head(20).iterrows():
        is_valid = True
        for req_col in schema["required"]:
            mapped = None
            for orig, std in col_mapping.items():
                if std == req_col:
                    mapped = orig
                    break
            if mapped and mapped in row and pd.notna(row[mapped]):
                continue
            if req_col == "station_code":
                if station_code_override:
                    continue
            is_valid = False
        if is_valid:
            valid_rows += 1
        else:
            invalid_rows += 1

    return {
        "success": True,
        "data_type": data_type,
        "total_rows": len(df),
        "column_mapping": col_mapping,
        "missing_required": missing_required,
        "sample_rows": sample_rows_clean,
        "estimated_stations": sorted(estimated_stations),
        "potential_issues": issues,
        "import_preview": {
            "valid_rows": valid_rows * (len(df) // max(20, 1)),
            "invalid_rows": invalid_rows * (len(df) // max(20, 1)),
            "stations_to_create": [] if missing_required else [],
        },
    }


def get_template_columns(data_type: str) -> dict:
    """获取导入模板信息"""
    schema = COLUMN_SCHEMAS.get(data_type)
    if not schema:
        return {"data_type": data_type, "columns": [], "example_row": {}}

    all_cols = schema["required"] + schema["optional"]
    columns = []
    for col in all_cols:
        columns.append({
            "name": col,
            "required": col in schema["required"],
            "description": _column_description(col, data_type),
        })

    example = _example_row(data_type)

    return {"data_type": data_type, "columns": columns, "example_row": example}


def _column_description(col: str, data_type: str) -> str:
    descs = {
        "station_code": "测站编号",
        "measurement_time": "监测时间 (YYYY-MM-DD HH:MM)",
        "acquisition_time": "影像获取时间 (YYYY-MM-DD)",
        "water_level": "地下水位 (m)",
        "water_depth": "埋深 (m)",
        "temperature": "温度 (°C)",
        "conductivity": "电导率 (μS/cm)",
        "rainfall_amount": "降雨量 (mm)",
        "intensity": "降雨强度 (mm/h)",
        "duration_min": "持续时间 (分钟)",
        "pressure_value": "孔隙水压力 (kPa)",
        "dx": "东西向位移 (mm)",
        "dy": "南北向位移 (mm)",
        "dz": "垂直位移 (mm)",
        "hdop": "HDOP 水平精度",
        "vdop": "VDOP 垂直精度",
        "los_displacement": "视线向形变 (mm)",
        "coherence": "相干性 (0~1)",
        "incidence_angle": "入射角 (°)",
        "track_number": "轨道编号",
    }
    return descs.get(col, col)


def _example_row(data_type: str) -> dict:
    examples = {
        "groundwater": {
            "station_code": "GW-01",
            "measurement_time": "2026-01-01 08:00",
            "water_level": 45.20,
            "water_depth": 12.30,
            "temperature": 16.5,
            "conductivity": 320,
        },
        "rainfall": {
            "station_code": "R-01",
            "measurement_time": "2026-01-01",
            "rainfall_amount": 25.5,
            "intensity": 5.0,
            "duration_min": 120,
        },
        "pore_pressure": {
            "station_code": "PP-01",
            "measurement_time": "2026-01-01 08:00",
            "pressure_value": 128.5,
            "temperature": 18.2,
        },
        "gnss": {
            "station_code": "G-01",
            "measurement_time": "2026-01-01 00:00",
            "dx": 2.35,
            "dy": -1.28,
            "dz": 0.56,
            "hdop": 1.2,
        },
        "insar": {
            "station_code": "I-01",
            "acquisition_time": "2026-01-01",
            "los_displacement": -5.2,
            "coherence": 0.85,
            "incidence_angle": 38.5,
            "track_number": "T123",
        },
    }
    return examples.get(data_type, {})


def _label(data_type: str) -> str:
    return DATA_TYPE_LABEL_MAP.get(data_type, data_type)
