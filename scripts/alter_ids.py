import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "db", "monitoring_models.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove uuid import
content = content.replace("import uuid\n", "")

# 2. Remove datetime/timezone import (no longer used after _utcnow removal)
content = content.replace("from datetime import datetime, timezone\n\n", "")

# 3. Remove _uuid() function
content = content.replace('''def _uuid() -> str:
    return str(uuid.uuid4())


''', "")

# 4. Replace all id columns from String(36) UUID to Integer autoincrement
import re
content = re.sub(
    r'id = Column\(String\(36\), primary_key=True, default=_uuid\)',
    'id = Column(Integer, primary_key=True, autoincrement=True)',
    content
)

# 5. Replace all station_id columns from String(36) to Integer
content = re.sub(
    r"station_id = Column\(String\(36\), ForeignKey\(\"monitoring_stations\.id\", ondelete=\"RESTRICT\"\)",
    'station_id = Column(Integer, ForeignKey("monitoring_stations.id", ondelete="RESTRICT")',
    content
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done. All IDs changed to Integer auto-increment.")
