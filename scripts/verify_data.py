import sys, os, openpyxl
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import create_engine, text

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "monitoring_data.db")
engine = create_engine("sqlite:///" + db.replace("\\", "/"), pool_size=1)

def pt(v):
    if v is None: return None
    if isinstance(v, datetime): return v
    if isinstance(v, str):
        v = v.strip()
        if not v: return None
        for f in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try: return datetime.strptime(v, f)
            except: continue
    return None

def tf(v):
    if v is None: return None
    try: return round(float(v), 4)
    except: return None

wb = openpyxl.load_workbook(r"C:\Users\24622\Desktop\监测数据2020.5.30-2026.6.10.xlsx", data_only=True)
ws = wb["监测数据合集"]

OK = "OK"; FAIL = "ERR"

with engine.connect() as c:
    print("=== GNS01 (G1) 抽样核对 ===")
    sid = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code='GNS01'")).scalar()
    err = 0
    for r in [2,3,5,10,100,500,1000,1500,2000,2097,2098,5594]:
        et = pt(ws.cell(r,7).value); edx=tf(ws.cell(r,8).value); edy=tf(ws.cell(r,9).value); edz=tf(ws.cell(r,10).value)
        if edx is not None and edy is not None and edz is not None:
            dr = c.execute(text("SELECT dx,dy,dz FROM gnss_measurements WHERE station_id=:s AND measurement_time=:t ORDER BY id"),{"s":sid,"t":et}).fetchall()
            if dr:
                found_match = False
                for d in dr:
                    if round(d[0],4)==edx and round(d[1],4)==edy and round(d[2],4)==edz:
                        found_match = True
                        break
                m = OK if found_match else FAIL
                if m==FAIL: err+=1; print(f"  Row {r} {str(et)[:10]}: X({edx},{edy},{edz}) DB中{len(dr)}条记录但无一匹配 {FAIL}")
                else: print(f"  Row {r} {str(et)[:10]}: X({edx},{edy},{edz}) DB({len(dr)}条) {OK}")
            else:
                err+=1; print(f"  Row {r} {str(et)[:10]}: X({edx}) DB(None) {FAIL}")
    print(f"GNS01 errors (the 5594 is 2nd segment, check below): {err}")

    # Verify the 5594 row data exists
    print(f"\nG1 second segment at 2025-06-20: ", end="")
    rows = c.execute(text("SELECT id,measurement_time,dx,dy,dz FROM gnss_measurements WHERE station_id=:s AND measurement_time='2025-06-20 00:00:00' ORDER BY id"),{"s":sid}).fetchall()
    for r in rows: print(f"ID={r[0]} dx={r[2]:.1f} dy={r[3]:.1f} dz={r[4]:.1f}  ", end="")
    print()

    print("\n=== 降雨量 (RFS-01) 核对 (修复 0.0 bug) ===")
    sid2 = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code='RFS-01'")).scalar()
    err2 = 0
    for r in [2,3,10,100,500,1000,1500,2000,2203]:
        et=pt(ws.cell(r,1).value); er=tf(ws.cell(r,2).value)
        if er is not None:
            dr = c.execute(text("SELECT rainfall_amount FROM rainfall_measurements WHERE station_id=:s AND measurement_time=:t"),{"s":sid2,"t":et}).scalar()
            dr = round(dr,4) if dr is not None else None
            m = OK if dr==er else FAIL
            if m==FAIL: err2+=1
            print(f"  Row {r} {str(et)[:10]}: X({er}) DB({dr}) {m}")
    print(f"Rainfall errors: {err2}")

    print("\n=== 地下水 DXS01 ===")
    sid3 = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code='DXS01'")).scalar()
    err3=0
    for r in [1511,1520,1800,2000,2200,2203]:
        et=pt(ws.cell(r,1).value); ew=tf(ws.cell(r,3).value)
        if ew is not None:
            dw = c.execute(text("SELECT water_level FROM groundwater_measurements WHERE station_id=:s AND measurement_time=:t"),{"s":sid3,"t":et}).scalar()
            dw = round(dw,4) if dw is not None else None
            m = OK if dw==ew else FAIL
            if m==FAIL: err3+=1
            print(f"  Row {r} {str(et)[:10]}: X({ew}) DB({dw}) {m}")
    print(f"Groundwater errors: {err3}")

    print("\n=== GNS02/03/04 抽样 ===")
    for code,tc,dc in [("GNS02",16,17),("GNS03",25,26),("GNS04",34,35)]:
        sid4 = c.execute(text("SELECT id FROM monitoring_stations WHERE station_code=:c"),{"c":code}).scalar()
        e4=0
        for r in [2,3,100,2200,2204]:
            et=pt(ws.cell(r,tc).value); ex=tf(ws.cell(r,dc).value)
            if et and ex:
                dx = c.execute(text("SELECT dx FROM gnss_measurements WHERE station_id=:s AND measurement_time=:t"),{"s":sid4,"t":et}).scalar()
                dx = round(dx,4) if dx is not None else None
                m = OK if dx==ex else FAIL
                if m==FAIL: e4+=1
                print(f"  {code} Row {r} {str(et)[:10]}: X({ex}) DB({dx}) {m}")
        print(f"  {code} errors: {e4}")

wb.close()
print(f"\nFinal: GNS01={err}, RFS={err2}, GW={err3}")
