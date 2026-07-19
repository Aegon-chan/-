import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import create_engine, text

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "monitoring_data.db")
engine = create_engine("sqlite:///" + db.replace("\\", "/"))

with engine.connect() as c:
    sid = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code='GNS01'")).scalar()
    # Find the records in the second segment (time jump backward)
    cnt = c.execute(text("""
        SELECT COUNT(*) FROM gnss_measurements g1
        WHERE station_id=:s AND id > (
            SELECT MIN(g2.id) FROM gnss_measurements g2 
            WHERE g2.station_id=:s AND g2.measurement_time < (
                SELECT measurement_time FROM gnss_measurements 
                WHERE station_id=:s ORDER BY id DESC LIMIT 1 OFFSET 310
            )
        )
    """), {"s": sid}).scalar()
    print(f"Records to delete: {cnt}")
    
    # Actually, let's find the exact split: ID where time jumps backward
    row = c.execute(text("""
        SELECT g1.id, g1.measurement_time, g2.id, g2.measurement_time
        FROM gnss_measurements g1
        JOIN gnss_measurements g2 ON g1.id = g2.id - 1
        WHERE g1.station_id=:s AND g2.station_id=:s
          AND g2.measurement_time < g1.measurement_time
        ORDER BY g1.id
        LIMIT 1
    """), {"s": sid, "s": sid}).fetchone()
    if row:
        split_id = row[0] + 1
        print(f"Split found: ID={split_id} (time jumps from {row[1]} to {row[3]})")
        
        with engine.begin() as conn:
            result = conn.execute(text("DELETE FROM gnss_measurements WHERE station_id=:s AND id >= :split"),
                                 {"s": sid, "split": split_id})
            print(f"Deleted {result.rowcount} rows")
    
    cnt2 = c.execute(text("SELECT COUNT(*) FROM gnss_measurements WHERE station_id=:s"), {"s": sid}).scalar()
    print(f"GNS01 remaining rows: {cnt2}")
