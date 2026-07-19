import sys, math
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

df = pd.DataFrame({
    "id": [1, 2, 3],
    "station_id": ["A", "B", "C"],
    "dx": [1.0, np.nan, 3.0],
    "dy": [np.nan, 2.0, np.nan],
})
df2 = df.copy()

def _clean_val(v):
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    return v

df_clean = df2.map(_clean_val)

# Check before json
for row in df_clean.to_dict(orient="records"):
    for k, v in row.items():
        ok = not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
        print(f"  {k}={v!r} ({type(v).__name__}) nan_ok={ok}")

# Check after json
import json
records = df_clean.to_dict(orient="records")
serialized = json.loads(json.dumps(records, default=str))
has_nan = False
for row in serialized:
    for k, v in row.items():
        is_bad = isinstance(v, float) and (math.isnan(v) or math.isinf(v))
        if is_bad:
            has_nan = True
            print(f"  BAD: {k}={v!r}")
if not has_nan:
    print("PASS: No NaN after json round-trip")
else:
    print("FAIL: NaN still present after json round-trip")

# Check repr() of the serialized data
repr_str = repr(serialized)
if " nan" in repr_str or "[nan" in repr_str:
    print("FAIL: bare 'nan' found in repr() output")
    # Find first occurrence
    idx = repr_str.find(" nan")
    if idx < 0:
        idx = repr_str.find("[nan")
    print(f"  Context: ...{repr_str[max(0,idx-50):idx+50]}...")
else:
    print("PASS: no bare 'nan' in repr() output")
