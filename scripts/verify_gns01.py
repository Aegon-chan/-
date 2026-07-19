import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import create_engine, text

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "monitoring_data.db")
engine = create_engine("sqlite:///" + db.replace("\\", "/"))

with engine.connect() as c:
    sid = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code='GNS01'")).scalar()
    total = c.execute(text("SELECT COUNT(*) FROM gnss_measurements WHERE station_id=:s"), {"s": sid}).scalar()
    first = c.execute(text("SELECT MIN(id),MIN(measurement_time) FROM gnss_measurements WHERE station_id=:s"), {"s": sid}).fetchone()
    last = c.execute(text("SELECT MAX(id),MAX(measurement_time) FROM gnss_measurements WHERE station_id=:s"), {"s": sid}).fetchone()
    span = c.execute(text("SELECT measurement_time FROM gnss_measurements WHERE station_id=:s ORDER BY id"), {"s": sid}).fetchall()
    print(f"GNS01: {total} rows")
    print(f"  First: ID={first[0]}, {first[1]}")
    print(f"  Last:  ID={last[0]}, {last[1]}")
    print(f"  Range: {span[0][0]} ~ {span[-1][0]}")
    
    # Check no more time jumps
    has_jump = c.execute(text("""
        SELECT COUNT(*) FROM gnss_measurements g1
        JOIN gnss_measurements g2 ON g1.id = g2.id - 1
        WHERE g1.station_id=:s AND g2.station_id=:s
          AND g2.measurement_time < g1.measurement_time
    """), {"s": sid, "s": sid}).scalar()
    print(f"  Time jumps: {has_jump}")

    # Check no duplicate times
    dup = c.execute(text("""
        SELECT COUNT(*) FROM gnss_measurements WHERE station_id=:s
        GROUP BY measurement_time HAVING COUNT(*) > 1
    """), {"s": sid}).scalar()
    print(f"  Duplicate measurement_time: {dup}")
