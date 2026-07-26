"""监测数据库种子数据生成。

生成 1 年半（2025-01-01 ~ 2026-07-07）的模拟监测数据：
- 3 个地下水监测井 → 每日水位
- 3 个雨量站 → 每日降雨量
- 2 个孔压计 → 每周孔压
- 2 个 GNSS 站 → 每日位移
- 2 个 InSAR 参考点 → 每 14 天形变

生成约 4000+ 行数据，用于测试和演示。
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta

import numpy as np

from backend.db.monitoring_session import SyncSessionLocal, sync_engine, MonitoringBase
from backend.db.monitoring_models import (
    GnssMeasurement,
    GroundwaterMeasurement,
    InSARMeasurement,
    MonitoringStation,
    PorePressureMeasurement,
    RainfallMeasurement,
    get_model_for_data_type,
    get_time_column_name,
)

logger = logging.getLogger("research_agent.seed_data")

random.seed(42)
np.random.seed(42)

# ============================================================
# 站点定义
# ============================================================

STATIONS = [
    # (code, name, type, lng, lat, alt, desc)
    ("GW-01", "ZK1# 监测井", "groundwater", 104.12, 30.55, 450.0, "滑坡体前缘"),
    ("GW-02", "ZK2# 监测井", "groundwater", 104.15, 30.58, 420.0, "滑坡体中部"),
    ("GW-03", "ZK3# 监测井", "groundwater", 104.08, 30.52, 480.0, "滑坡体后缘"),
    ("R-01", "雨量站1号", "rainfall", 104.10, 30.56, 460.0, "滑坡体顶部"),
    ("R-02", "雨量站2号", "rainfall", 104.18, 30.53, 430.0, "河谷北岸"),
    ("R-03", "雨量站3号", "rainfall", 104.05, 30.60, 500.0, "山脊南侧"),
    ("PP-01", "孔压计1号", "pore_pressure", 104.12, 30.55, 450.0, "ZK1 旁"),
    ("PP-02", "孔压计2号", "pore_pressure", 104.15, 30.58, 420.0, "ZK2 旁"),
    ("G-01", "GNSS监测点1号", "gnss", 104.13, 30.56, 455.0, "坡体中部"),
    ("G-02", "GNSS监测点2号", "gnss", 104.09, 30.54, 470.0, "坡体后缘"),
    ("I-01", "InSAR参考点1号", "insar", 104.12, 30.55, 450.0, "同 ZK1"),
    ("I-02", "InSAR参考点2号", "insar", 104.15, 30.58, 420.0, "同 ZK2"),
]


def _uuid() -> str:
    return str(uuid.uuid4())


def seed_monitoring_data(overwrite: bool = False) -> dict:
    """填充监测数据库种子数据。

    Args:
        overwrite: 是否覆盖已有数据

    Returns:
        各类型数据统计
    """
    MonitoringBase.metadata.create_all(sync_engine)
    session = SyncSessionLocal()
    try:
        # Check if data already exists
        existing_stations = session.query(MonitoringStation).count()
        if existing_stations > 0 and not overwrite:
            logger.info("监测数据库已有数据 (%d 个站点)，跳过种子生成", existing_stations)
            # Just return stats
            return _get_stats(session)

        # Clear existing data if overwriting
        if overwrite:
            for model in [InSARMeasurement, GnssMeasurement, PorePressureMeasurement,
                          RainfallMeasurement, GroundwaterMeasurement]:
                session.query(model).delete()
            session.query(MonitoringStation).delete()
            session.commit()

        # 1. Create stations
    station_ids = {}
    for code, name, stype, lng, lat, alt, desc in STATIONS:
        station = MonitoringStation(
                station_code=code,
                station_name=name,
                station_type=stype,
                longitude=lng,
                latitude=lat,
                altitude=alt,
                description=desc,
                status="active",
            )
            session.add(station)
            session.flush()
            station_ids[code] = station.id
        session.commit()
        logger.info("已创建 %d 个监测站点", len(STATIONS))

        # 2. Generate time series data
        start_date = datetime(2025, 1, 1, 8, 0, 0)
        end_date = datetime(2026, 7, 7, 8, 0, 0)
        total_days = (end_date - start_date).days
        dates_daily = [start_date + timedelta(days=i) for i in range(total_days + 1)]

        total = 0

        # --- Groundwater: daily water level ---
        gw_base = {"GW-01": 45.0, "GW-02": 62.0, "GW-03": 38.0}
        gw_seasonal_amp = {"GW-01": 3.0, "GW-02": 4.0, "GW-03": 2.5}
        gw_trend_slope = {"GW-01": -0.003, "GW-02": -0.005, "GW-03": -0.002}

        for code in ["GW-01", "GW-02", "GW-03"]:
            sid = station_ids[code]
            base = gw_base[code]
            amp = gw_seasonal_amp[code]
            slope = gw_trend_slope[code]
            objs = []
            for i, dt in enumerate(dates_daily):
                # Seasonal: high in summer (July), low in winter (January)
                season = amp * np.sin(2 * np.pi * (i / 365.0 - 0.25))
                trend = slope * i
                noise = np.random.normal(0, 0.15)
                # Rainfall response: occasional sharp rises
                rain_effect = 0
                if np.random.random() < 0.03:
                    rain_effect = np.random.uniform(0.3, 1.2)

                wl = round(base + season + trend + noise + rain_effect, 2)
                wd = round(abs(wl - base) + np.random.uniform(10, 15), 2)
                temp = round(16 + 8 * np.sin(2 * np.pi * (i / 365.0 - 0.25)) + np.random.normal(0, 0.5), 1)
                cond = round(300 + 50 * np.sin(2 * np.pi * (i / 365.0)) + np.random.normal(0, 20), 0)

                objs.append(GroundwaterMeasurement(
                    station_id=sid, measurement_time=dt,
                    water_level=wl, water_depth=wd, temperature=temp,
                    conductivity=cond,
                ))
            session.bulk_save_objects(objs)
            session.commit()
            total += len(objs)
        logger.info("已生成地下水位数据: %d 条", total - (total - len(dates_daily) * 3))

        # --- Rainfall: daily rainfall ---
        # Seasonal pattern: wet season May-Sep, dry season Nov-Mar
        rain_codes = ["R-01", "R-02", "R-03"]
        rain_scale = {"R-01": 1.0, "R-02": 0.85, "R-03": 1.15}

        for code in rain_codes:
            sid = station_ids[code]
            scale = rain_scale[code]
            objs = []
            for dt in dates_daily:
                month = dt.month
                # Base probability of rain
                if 5 <= month <= 9:
                    rainy_prob = 0.45
                    base_amount = np.random.exponential(8.0)
                elif month in [4, 10]:
                    rainy_prob = 0.30
                    base_amount = np.random.exponential(5.0)
                else:
                    rainy_prob = 0.15
                    base_amount = np.random.exponential(3.0)

                if np.random.random() < rainy_prob:
                    amount = round(base_amount * scale, 1)
                    # Occasionally heavy rain
                    if np.random.random() < 0.02 and 5 <= month <= 9:
                        amount = round(amount * np.random.uniform(3, 6), 1)  # 暴雨
                    intensity = round(amount / max(1, np.random.uniform(0.5, 6)), 1)
                    duration = int(np.random.uniform(30, 360))
                else:
                    amount = 0.0
                    intensity = 0.0
                    duration = 0

                objs.append(RainfallMeasurement(
                    station_id=sid, measurement_time=dt,
                    rainfall_amount=amount, intensity=intensity, duration_min=duration,
                ))
            session.bulk_save_objects(objs)
            session.commit()
            total += len(objs)

        # --- Pore Pressure: weekly ---
        pp_codes = ["PP-01", "PP-02"]
        pp_base = {"PP-01": 125.0, "PP-02": 98.0}
        dates_weekly = [start_date + timedelta(days=i * 7) for i in range(total_days // 7 + 1)]
        dates_weekly = [d for d in dates_weekly if d <= end_date]

        for code in pp_codes:
            sid = station_ids[code]
            base = pp_base[code]
            objs = []
            for i, dt in enumerate(dates_weekly):
                season = 15.0 * np.sin(2 * np.pi * (i * 7 / 365.0 - 0.2))
                trend = -0.02 * (i * 7)
                noise = np.random.normal(0, 2.0)
                # Rainfall response (with 1-2 day lag simulated by weekly sampling)
                rain_response = 0
                if np.random.random() < 0.15:
                    rain_response = np.random.uniform(3, 15)

                pv = round(base + season + trend + noise + rain_response, 2)
                temp = round(16 + 8 * np.sin(2 * np.pi * (i * 7 / 365.0 - 0.25)) + np.random.normal(0, 0.8), 1)

                objs.append(PorePressureMeasurement(
                    station_id=sid, measurement_time=dt,
                    pressure_value=pv, temperature=temp,
                ))
            session.bulk_save_objects(objs)
            session.commit()
            total += len(objs)

        # --- GNSS: daily displacement ---
        gnss_codes = ["G-01", "G-02"]
        gnss_base_velocity = {"G-01": {"dx": 2.5, "dy": -1.5, "dz": 1.0},
                              "G-02": {"dx": 1.8, "dy": -0.8, "dz": 0.6}}

        for code in gnss_codes:
            sid = station_ids[code]
            vel = gnss_base_velocity[code]
            objs = []
            for i, dt in enumerate(dates_daily):
                # Cumulative displacement with daily noise
                noise_scale = 0.3
                dx = round(vel["dx"] * (i / 365.0) + np.random.normal(0, noise_scale), 3)
                dy = round(vel["dy"] * (i / 365.0) + np.random.normal(0, noise_scale), 3)
                dz = round(vel["dz"] * (i / 365.0) + np.random.normal(0, noise_scale), 3)
                # Acceleration during rainy season
                if 5 <= dt.month <= 9:
                    rain_accel = 0.005 * np.random.uniform(0, 1)
                    dx += round(rain_accel * (i / 365.0), 3)
                    dy -= round(rain_accel * 0.6 * (i / 365.0), 3)

                hdop = round(np.random.uniform(0.8, 2.5), 1)
                vdop = round(np.random.uniform(1.5, 4.0), 1)

                objs.append(GnssMeasurement(
                    station_id=sid, measurement_time=dt,
                    dx=dx, dy=dy, dz=dz, hdop=hdop, vdop=vdop,
                ))
            session.bulk_save_objects(objs)
            session.commit()
            total += len(objs)

        # --- InSAR: bi-weekly ---
        insar_codes = ["I-01", "I-02"]
        insar_base_trend = {"I-01": -3.5, "I-02": -2.0}

        dates_biweekly = [start_date + timedelta(days=i * 14) for i in range(total_days // 14 + 1)]
        dates_biweekly = [d for d in dates_biweekly if d <= end_date]

        for code in insar_codes:
            sid = station_ids[code]
            trend = insar_base_trend[code]
            objs = []
            for i, dt in enumerate(dates_biweekly):
                # Cumulative LOS displacement
                cumulative = trend * (i * 14 / 365.0)
                seasonal = 2.0 * np.sin(2 * np.pi * (i * 14 / 365.0 - 0.3))
                noise = np.random.normal(0, 0.5)
                los = round(cumulative + seasonal + noise, 2)

                coherence = round(max(0.3, min(0.98, np.random.beta(8, 2))), 3)
                inc_angle = round(np.random.uniform(34, 42), 1)
                track = f"T{np.random.randint(120, 130)}"

                objs.append(InSARMeasurement(
                    station_id=sid, acquisition_time=dt,
                    los_displacement=los, coherence=coherence,
                    incidence_angle=inc_angle, track_number=track,
                ))
            session.bulk_save_objects(objs)
            session.commit()
            total += len(objs)

        logger.info("种子数据生成完成，共 %d 条记录", total)

        stats = _get_stats(session)
        stats["total"] = total
        return stats

    finally:
        session.close()


def _get_stats(session) -> dict:
    """获取当前数据量统计"""
    from sqlalchemy import func
    stats = {}
    for model, name in [
        (MonitoringStation, "stations"),
        (GroundwaterMeasurement, "groundwater"),
        (RainfallMeasurement, "rainfall"),
        (PorePressureMeasurement, "pore_pressure"),
        (GnssMeasurement, "gnss"),
        (InSARMeasurement, "insar"),
    ]:
        count = session.query(func.count(model.id)).scalar() or 0
        stats[name] = count
    return stats


def clear_all_data():
    """清空所有监测数据"""
    session = SyncSessionLocal()
    try:
        for model in [InSARMeasurement, GnssMeasurement, PorePressureMeasurement,
                      RainfallMeasurement, GroundwaterMeasurement, MonitoringStation]:
            session.query(model).delete()
        session.commit()
        logger.info("已清空所有监测数据")
    finally:
        session.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    result = seed_monitoring_data(overwrite=True)
    print(f"种子数据统计: {result}")
