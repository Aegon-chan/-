import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import create_engine, text
import backend.db.monitoring_models  # noqa: F401

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "monitoring_data.db")
engine = create_engine("sqlite:///" + db.replace("\\", "/"))

with engine.connect() as c:
    print("=== Stations (auto-increment IDs) ===")
    rows = c.execute(text("SELECT id, station_code, station_type FROM monitoring_stations ORDER BY id")).fetchall()
    for r in rows:
        print(f"  ID={r[0]}  {r[1]} ({r[2]})")

    print("\n=== Row counts ===")
    for t in ["monitoring_stations", "rainfall_measurements", "groundwater_measurements", "gnss_measurements"]:
        cnt = c.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"  {t}: {cnt} rows")

    print("\n=== Sample data (gnss with auto-increment IDs) ===")
    rows = c.execute(text("""
        SELECT g.id, s.station_code, g.measurement_time, g.dx, g.dy
        FROM gnss_measurements g JOIN monitoring_stations s ON g.station_id = s.id
        WHERE s.station_code = 'GNS01'
        ORDER BY g.id LIMIT 3
    """)).fetchall()
    for r in rows:
        print(f"  ID={r[0]}  {r[1]}  {r[2]}  dx={r[3]:.1f}  dy={r[4]:.1f}")

    print("\n=== Sample data (groundwater with auto-increment IDs) ===")
    rows = c.execute(text("""
        SELECT g.id, s.station_code, g.measurement_time, g.water_level
        FROM groundwater_measurements g JOIN monitoring_stations s ON g.station_id = s.id
        ORDER BY g.id LIMIT 3
    """)).fetchall()
    for r in rows:
        print(f"  ID={r[0]}  {r[1]}  {r[2]}  water_level={r[3]}")
