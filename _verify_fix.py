import sys, math, json
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from backend.analysis.data_loader import dataframe_to_sandbox_context
import pandas as pd
import numpy as np

df = pd.DataFrame({
    "id": [1, 2, 3],
    "station_id": ["A", "B", "C"],
    "dx": [1.0, np.nan, 3.0],
    "dy": [np.nan, 2.0, np.nan],
    "dz": [0.5, 1.5, np.nan],
    "measurement_time": pd.to_datetime(["2020-05-30", "2020-05-31", "2020-06-01"]),
})
df.set_index("measurement_time", inplace=True)

ctx = dataframe_to_sandbox_context(df)
records = ctx["df"]

def has_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return True
    if isinstance(obj, dict):
        return any(has_nan(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_nan(v) for v in obj)
    return False

if has_nan(records):
    print("FAIL: NaN/Inf values still present")
    sys.exit(1)
else:
    print("PASS: No NaN/Inf values")

for row in records:
    for k, v in row.items():
        if v is not None:
            eval(repr(v))
print("PASS: repr() of all values produces valid Python")
print("Row count:", len(records))
print("Columns:", ctx["_col_names"])
print("Types:", ctx["_col_dtypes"])

# Now test the sandbox wrapper build
from backend.core.sandbox_providers import build_wrapper
code = "df = pd.DataFrame(df)\nprint('shape:', df.shape)"
wrapped = build_wrapper(code, context=ctx)
print("PASS: build_wrapper succeeded")
print("Wrapped script size:", len(wrapped), "bytes")

# Show that df = [...] line has no bare 'nan' or 'inf'
import re
df_line = re.search(r"    df = \[", wrapped)
if df_line:
    df_start = df_line.start()
    context_end = wrapped.find(")", df_start)
    context_snippet = wrapped[df_start:df_start+500]
    if " nan" in context_snippet or "nan," in context_snippet:
        print("FAIL: bare 'nan' found in injected code")
        sys.exit(1)
    else:
        print("PASS: no bare 'nan' tokens in injected code")
