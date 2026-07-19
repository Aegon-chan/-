path = r"C:\Users\24622\Desktop\科研Agent\backend\db\monitoring_models.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove hdop, vdop
content = content.replace("    hdop = Column(Float, nullable=True)                # 水平精度因子\n", "")
content = content.replace("    vdop = Column(Float, nullable=True)                # 垂直精度因子\n", "")

# Add new fields before the station relationship
old = """    dz = Column(Float, nullable=False)                 # 垂直向位移 (mm)

    station = relationship(\"MonitoringStation\", back_populates=\"gnss_measurements\")"""

new = """    dz = Column(Float, nullable=False)                 # 垂直向位移 (mm)
    planar_displacement = Column(Float, nullable=True)     # 平面位移 (mm)
    variation = Column(Float, nullable=True)               # 变化量 (mm)
    daily_planar_rate = Column(Float, nullable=True)       # 日平面位移速率 (mm/d)
    daily_variation_rate = Column(Float, nullable=True)    # 日变化量速率 (mm/d)

    station = relationship(\"MonitoringStation\", back_populates=\"gnss_measurements\")"""

content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated gnss fields")

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import create_engine, inspect, text
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "monitoring_data.db")
uri = "sqlite:///" + db_path.replace("\\", "/")
engine = create_engine(uri, echo=False)

for t in inspect(engine).get_table_names():
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{t}"'))

import backend.db.monitoring_models  # noqa: F401
from backend.db.monitoring_session import MonitoringBase
MonitoringBase.metadata.create_all(engine)

for t in inspect(engine).get_table_names():
    cols = [c["name"] for c in inspect(engine).get_columns(t)]
    print(f"  {t}: {cols}")
