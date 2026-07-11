"""Integration test for monitoring data importer."""
from __future__ import annotations

import pytest
import pandas as pd
from datetime import datetime

from backend.analysis.monitoring_importer import (
    import_from_df,
    normalize_columns,
    parse_time,
)


@pytest.fixture(scope="module")
def monitoring_db():
    from backend.db.monitoring_session import sync_engine, MonitoringBase
    from backend.db.monitoring_models import (
        MonitoringStation, GroundwaterMeasurement, RainfallMeasurement,
        PorePressureMeasurement, GnssMeasurement, InSARMeasurement, ImportBatch,
    )
    from sqlalchemy import text
    MonitoringBase.metadata.create_all(bind=sync_engine)
    yield
    tables = [
        GroundwaterMeasurement.__tablename__,
        RainfallMeasurement.__tablename__,
        PorePressureMeasurement.__tablename__,
        GnssMeasurement.__tablename__,
        InSARMeasurement.__tablename__,
        ImportBatch.__tablename__,
        MonitoringStation.__tablename__,
    ]
    with sync_engine.connect() as conn:
        for table in reversed(tables):
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()


class TestMonitoringImporter:

    @pytest.mark.asyncio
    async def test_import_groundwater_success(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["GW-TEST1"],
            "measurement_time": ["2026-07-01 08:00"],
            "water_level": [45.2],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1

    @pytest.mark.asyncio
    async def test_import_rainfall_success(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["R-TEST1"],
            "measurement_time": ["2026-07-01"],
            "rainfall_amount": [25.5],
            "intensity": [5.0],
            "duration_min": [120],
        })
        result = await import_from_df(df, "rainfall", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1

    @pytest.mark.asyncio
    async def test_import_gnss_success(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["G-TEST1"],
            "measurement_time": ["2026-07-01 00:00"],
            "dx": [2.35],
            "dy": [-1.28],
            "dz": [0.56],
            "hdop": [1.2],
        })
        result = await import_from_df(df, "gnss", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1

    @pytest.mark.asyncio
    async def test_import_insar_success(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["I-TEST1"],
            "acquisition_time": ["2026-07-01"],
            "los_displacement": [-5.2],
            "coherence": [0.85],
            "incidence_angle": [38.5],
            "track_number": ["T123"],
        })
        result = await import_from_df(df, "insar", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1

    @pytest.mark.asyncio
    async def test_import_multiple_rows(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["GW-MULTI1", "GW-MULTI1", "GW-MULTI1"],
            "measurement_time": ["2026-07-01 08:00", "2026-07-02 08:00", "2026-07-03 08:00"],
            "water_level": [45.2, 45.1, 44.9],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 3

    @pytest.mark.asyncio
    async def test_missing_required_column(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["GW-ERR1"],
            "measurement_time": ["2026-07-01 08:00"],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is False
        assert result["imported"] == 0

    @pytest.mark.asyncio
    async def test_empty_station_code(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["", "GW-OK1"],
            "measurement_time": ["2026-07-01 08:00", "2026-07-01 08:00"],
            "water_level": [45.2, 44.8],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_invalid_time_format(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["GW-TIME1"],
            "measurement_time": ["not-a-date"],
            "water_level": [45.2],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is False
        assert result["imported"] == 0

    @pytest.mark.asyncio
    async def test_station_code_override_missing(self, monitoring_db):
        df = pd.DataFrame({
            "measurement_time": ["2026-07-01 08:00"],
            "water_level": [45.2],
        })
        result = await import_from_df(df, "groundwater", station_code_override="GW-OVERRIDE1", create_stations=True)
        assert result["success"] is False
        assert "缺少" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_roundtrip_db_query(self, monitoring_db):
        df = pd.DataFrame({
            "station_code": ["GW-ROUND1"],
            "measurement_time": ["2026-07-01 08:00"],
            "water_level": [45.2],
        })
        result = await import_from_df(df, "groundwater", create_stations=True)
        assert result["success"] is True
        assert result["imported"] == 1
        from backend.db.monitoring_session import SyncSessionLocal
        from backend.db.monitoring_models import MonitoringStation, GroundwaterMeasurement
        from sqlalchemy import select
        with SyncSessionLocal() as session:
            stmt = select(MonitoringStation).where(MonitoringStation.station_code == "GW-ROUND1")
            station = session.execute(stmt).scalar_one_or_none()
            assert station is not None
            assert station.station_type == "groundwater"
            stmt2 = select(GroundwaterMeasurement).where(GroundwaterMeasurement.station_id == station.id)
            msmt = session.execute(stmt2).scalar_one_or_none()
            assert msmt is not None
            assert msmt.water_level == 45.2

    def test_normalize_columns_exact_match(self):
        df = pd.DataFrame(columns=["station_code", "measurement_time", "water_level"])
        matched, mapping, missing = normalize_columns(df, "groundwater")
        assert "station_code" in matched
        assert len(missing) == 0

    def test_normalize_columns_missing_required(self):
        df = pd.DataFrame(columns=["station_code"])
        matched, mapping, missing = normalize_columns(df, "groundwater")
        assert "measurement_time" in missing or "water_level" in missing

    def test_parse_time_iso_format(self):
        result = parse_time("2026-07-01 08:00:00")
        assert result is not None
        assert result.year == 2026 and result.month == 7

    def test_parse_time_date_only(self):
        assert parse_time("2026-07-01") is not None

    def test_parse_time_invalid(self):
        assert parse_time("not-a-date") is None

    def test_parse_time_empty(self):
        assert parse_time("") is None

    def test_parse_time_none(self):
        assert parse_time(None) is None
