"""Data file reading and schema extraction for NL2Query.

Reads uploaded CSV/XLSX files, extracts column schema + sample rows,
and prepares DataFrames for sandbox context injection.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger("research_agent.data_loader")

# ── Recognized file extensions ──
SPREADSHEET_EXTS = {".xlsx", ".xls", ".xlsm", ".xlsb"}
TABULAR_EXTS = {".csv", ".tsv", ".txt"} | SPREADSHEET_EXTS

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"


def _resolve_file_path(file_id: str) -> Optional[Path]:
    """Resolve a file_id (UUID filename or original filename) to an absolute path.

    Tries exact match first, then searches UPLOAD_DIR.
    """
    fp = UPLOAD_DIR / file_id
    if fp.exists():
        return fp
    # Search by prefix match (UUID filenames)
    if UPLOAD_DIR.exists():
        for child in UPLOAD_DIR.iterdir():
            if child.is_file() and child.name.startswith(file_id):
                return child
    return None


def list_uploaded_files() -> list[dict]:
    """List all uploaded tabular data files in the upload directory.

    Returns list of dicts with keys: id, filename, size, ext
    """
    files = []
    if not UPLOAD_DIR.exists():
        return files
    for child in sorted(UPLOAD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if child.is_file() and child.stat().st_size > 0:
            ext = child.suffix.lower()
            if ext in TABULAR_EXTS:
                files.append({
                    "id": child.name,
                    "filename": child.name,
                    "size": child.stat().st_size,
                    "ext": ext,
                })
    return files


def read_data_file(file_path: Path) -> Optional[pd.DataFrame]:
    """Read a CSV/TSV/XLSX file into a pandas DataFrame."""
    ext = file_path.suffix.lower()
    try:
        if ext == ".csv":
            return pd.read_csv(file_path, encoding="utf-8", low_memory=False)
        elif ext == ".tsv" or ext == ".txt":
            return pd.read_csv(file_path, sep="\t", encoding="utf-8", low_memory=False)
        elif ext in SPREADSHEET_EXTS:
            return pd.read_excel(file_path, engine="openpyxl" if ext != ".xls" else "xlrd")
        else:
            logger.warning("Unsupported file extension: %s", ext)
            return None
    except Exception as e:
        logger.exception("Failed to read data file %s: %s", file_path, e)
        return None


def extract_data_schema(df: pd.DataFrame) -> dict:
    """Extract column schema and sample data from a DataFrame.

    Returns a dict with keys:
        column_names, column_info, row_count, sample_rows, data_description_text
    """
    if df is None or df.empty:
        return {
            "column_names": [],
            "column_info": [],
            "row_count": 0,
            "sample_rows": [],
            "data_description_text": "(no data)",
        "time_range": time_range,
        }

    row_count = len(df)
    sample_rows = df.head(5).fillna("").to_dict(orient="records")

    column_info = []
    for col in df.columns:
        col_series = df[col]
        non_null = int(col_series.notna().sum())
        null_count = int(col_series.isna().sum())
        dtype = str(col_series.dtype)

        non_null_vals = col_series.dropna().unique()
        samples = [str(v) for v in non_null_vals[:3]]

        column_info.append({
            "name": col,
            "dtype": dtype,
            "non_null": non_null,
            "null_count": null_count,
            "sample_values": samples,
        })

    lines = [
        f"Data rows: {row_count}",
        f"Columns: {len(df.columns)}",
        "",
        "Column info:",
    ]
    for ci in column_info:
        samples_str = ", ".join(ci["sample_values"])
        null_str = f" ({ci['null_count']} missing)" if ci["null_count"] > 0 else ""
        lines.append(f"  - {ci['name']} ({ci['dtype']}){null_str}: samples [{samples_str}]")

    lines.append("")
    lines.append("First 5 sample rows:")
    for i, row in enumerate(sample_rows[:5], 1):
        vals = "; ".join(f"{k}={v}" for k, v in row.items())
        lines.append(f"  Row {i}: {vals}")

    # Detect datetime cols and compute time range
    time_range = None
    for col in df.columns:
        try:
            # Skip numeric columns (they would be interpreted as nanoseconds from epoch)
            col_dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(col_dtype) and "datetime" not in str(col_dtype):
                continue
            col_series = pd.to_datetime(df[col], errors="coerce")
            if col_series.notna().sum() > len(df) * 0.8:
                valid_dates = col_series.dropna()
                time_range = {"column": col, "start": valid_dates.min().strftime("%Y-%m-%d"), "end": valid_dates.max().strftime("%Y-%m-%d")}
                lines.append("Time range of " + col + ": " + time_range["start"] + " ~ " + time_range["end"])
                break
        except Exception:
            continue
    if time_range is None and isinstance(df.index, pd.DatetimeIndex):
        time_range = {"column": str(df.index.name or "index"), "start": df.index.min().strftime("%Y-%m-%d"), "end": df.index.max().strftime("%Y-%m-%d")}
        lines.append("Time range of index: " + time_range["start"] + " ~ " + time_range["end"])
    return {
        "column_names": list(df.columns),
        "column_info": column_info,
        "row_count": row_count,
        "sample_rows": sample_rows,
        "data_description_text": "\n".join(lines),
        "time_range": time_range,
    }


def dataframe_to_sandbox_context(df: pd.DataFrame) -> dict[str, Any]:
    """Convert a DataFrame into serializable variables for sandbox injection.

    NaN/Inf values are explicitly converted to None *after* the json round-trip,
    because pandas float64 columns silently coerce None back to NaN.
    This ensures repr() in the sandbox wrapper never emits bare ``nan``/``inf``
    tokens (which would cause NameError at runtime).
    """
    import json
    import math

    # Include named index (e.g. DatetimeIndex from monitoring data) as a regular column
    if df.index.name is not None and df.index.name not in df.columns:
        df = df.reset_index()

    records = df.to_dict(orient="records")
    serializable_records = json.loads(json.dumps(records, default=str, ensure_ascii=False))

    # Post-process: convert NaN/Inf back to None (json round-trip preserves NaN).
    def _clean(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean(v) for v in obj]
        return obj

    serializable_records = _clean(serializable_records)

    # Detect columns that were originally datetime (converted to str by JSON)
    _datetime_cols = []
    for col, dtype in df.dtypes.items():
        if "datetime" in str(dtype):
            _datetime_cols.append(col)
    # Also check if index was a DatetimeIndex and was reset
    if hasattr(df, "index") and isinstance(df.index, pd.DatetimeIndex) and df.index.name and df.index.name not in df.columns:
        pass  # Already covered by column detection after reset_index

    return {
        "df": serializable_records,
        "_col_names": list(df.columns),
        "_col_dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "_row_count": len(df),
        "_datetime_columns": _datetime_cols,
    }


def load_data_for_analysis(file_id: str) -> tuple[Optional[pd.DataFrame], Optional[dict], str]:
    """Load data file and extract schema. Top-level convenience.

    Returns (df, schema, error_message).
    On failure df and schema are None and error_message contains the error.
    """
    file_path = _resolve_file_path(file_id)
    if file_path is None:
        return None, None, f"Data file not found: {file_id}"

    df = read_data_file(file_path)
    if df is None:
        return None, None, f"Cannot read data file: {file_path.name}"

    schema = extract_data_schema(df)
    return df, schema, ""


__all__ = [
    "list_uploaded_files",
    "load_data_for_analysis",
    "extract_data_schema",
    "dataframe_to_sandbox_context",
    "read_data_file",
]
