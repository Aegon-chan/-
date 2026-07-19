# -*- coding: utf-8 -*-
"""监测数据库模型定义。

包含 1 个站点表 + 5 个分类数据表：
- monitoring_stations: 所有监测站点
- groundwater_measurements: 地下水位
- rainfall_measurements: 降雨量
- pore_pressure_measurements: 孔隙水压力
- gnss_measurements: GNSS 位移
- insar_measurements: InSAR 形变
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.db.monitoring_session import MonitoringBase


# ---------------------------------------------------------------------------
# 监测站点
# ---------------------------------------------------------------------------

class MonitoringStation(MonitoringBase):
    """监测站点"""
    __tablename__ = "monitoring_stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_code = Column(String(32), unique=True, nullable=False, index=True)
    station_name = Column(String(128), default="")
    station_type = Column(String(32), nullable=False, index=True)  # groundwater/rainfall/pore_pressure/gnss/insar
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    description = Column(Text, default="")
    status = Column(String(16), default="active")

    # 反向关联（各测量表）
    groundwater_measurements = relationship("GroundwaterMeasurement", back_populates="station",
                                            cascade="all, delete-orphan")
    rainfall_measurements = relationship("RainfallMeasurement", back_populates="station",
                                         cascade="all, delete-orphan")
    pore_pressure_measurements = relationship("PorePressureMeasurement", back_populates="station",
                                              cascade="all, delete-orphan")
    gnss_measurements = relationship("GnssMeasurement", back_populates="station",
                                     cascade="all, delete-orphan")
    insar_measurements = relationship("InSARMeasurement", back_populates="station",
                                      cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 地下水测量
# ---------------------------------------------------------------------------

class GroundwaterMeasurement(MonitoringBase):
    """地下水测量数据"""
    __tablename__ = "groundwater_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    measurement_time = Column(DateTime, nullable=False, index=True)
    water_level = Column(Float, nullable=False)       # 水位 (m)
    water_depth = Column(Float, nullable=True)         # 埋深 (m)
    temperature = Column(Float, nullable=True)         # 水温 (°C)

    station = relationship("MonitoringStation", back_populates="groundwater_measurements")


# ---------------------------------------------------------------------------
# 降雨量测量
# ---------------------------------------------------------------------------

class RainfallMeasurement(MonitoringBase):
    """降雨量测量数据"""
    __tablename__ = "rainfall_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    measurement_time = Column(DateTime, nullable=False, index=True)
    rainfall_amount = Column(Float, nullable=False)    # 降雨量 (mm)

    station = relationship("MonitoringStation", back_populates="rainfall_measurements")


# ---------------------------------------------------------------------------
# 孔隙水压力测量
# ---------------------------------------------------------------------------

class PorePressureMeasurement(MonitoringBase):
    """孔隙水压力测量数据"""
    __tablename__ = "pore_pressure_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    measurement_time = Column(DateTime, nullable=False, index=True)
    pressure_value = Column(Float, nullable=False)     # 孔隙水压力 (kPa)
    temperature = Column(Float, nullable=True)          # 温度 (°C)

    station = relationship("MonitoringStation", back_populates="pore_pressure_measurements")


# ---------------------------------------------------------------------------
# GNSS 位移测量
# ---------------------------------------------------------------------------

class GnssMeasurement(MonitoringBase):
    """GNSS 位移测量数据"""
    __tablename__ = "gnss_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    measurement_time = Column(DateTime, nullable=False, index=True)
    dx = Column(Float, nullable=False)                 # 东西向位移 (mm)
    dy = Column(Float, nullable=False)                 # 南北向位移 (mm)
    dz = Column(Float, nullable=False)                 # 垂直向位移 (mm)
    planar_displacement = Column(Float, nullable=True)     # 平面位移 (mm)
    variation = Column(Float, nullable=True)               # 变化量 (mm)
    daily_planar_rate = Column(Float, nullable=True)       # 日平面位移速率 (mm/d)
    daily_variation_rate = Column(Float, nullable=True)    # 日变化量速率 (mm/d)

    station = relationship("MonitoringStation", back_populates="gnss_measurements")


# ---------------------------------------------------------------------------
# InSAR 形变测量
# ---------------------------------------------------------------------------

class InSARMeasurement(MonitoringBase):
    """InSAR 形变测量数据"""
    __tablename__ = "insar_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    acquisition_time = Column(DateTime, nullable=False, index=True)  # 影像获取时间
    los_displacement = Column(Float, nullable=False)    # 视线向形变 (mm)
    coherence = Column(Float, nullable=True)             # 相干性
    incidence_angle = Column(Float, nullable=True)       # 入射角 (°)
    track_number = Column(String(32), nullable=True)     # 轨道编号

    station = relationship("MonitoringStation", back_populates="insar_measurements")


# ---------------------------------------------------------------------------
# 

class ImportBatch(MonitoringBase):
    """Import batch record for tracking uploaded data."""
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String(32), nullable=False, index=True)
    file_name = Column(String(256), default="")
    batch_label = Column(String(128), default="")
    total_rows = Column(Integer, default=0)
    imported_rows = Column(Integer, default=0)
    skipped_rows = Column(Integer, default=0)
    time_range_start = Column(DateTime, nullable=True)
    time_range_end = Column(DateTime, nullable=True)


# 工具函数：根据 data_type 获取对应的模型类
# ---------------------------------------------------------------------------

DATA_TYPE_MODEL_MAP = {
    "groundwater": GroundwaterMeasurement,
    "rainfall": RainfallMeasurement,
    "pore_pressure": PorePressureMeasurement,
    "gnss": GnssMeasurement,
    "insar": InSARMeasurement,
}

DATA_TYPE_LABEL_MAP = {
    "groundwater": "地下水",
    "rainfall": "降雨量",
    "pore_pressure": "孔隙水压力",
    "gnss": "GNSS",
    "insar": "InSAR",
}

DATA_TYPE_TIME_COLUMN_MAP = {
    "groundwater": "measurement_time",
    "rainfall": "measurement_time",
    "pore_pressure": "measurement_time",
    "gnss": "measurement_time",
    "insar": "acquisition_time",
}


def get_model_for_data_type(data_type: str):
    """根据 data_type 返回对应的测量模型类"""
    return DATA_TYPE_MODEL_MAP.get(data_type)


def get_time_column_name(data_type: str) -> str:
    """获取该数据类型的时间列名"""
    return DATA_TYPE_TIME_COLUMN_MAP.get(data_type, "measurement_time")
