from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("research_agent.parser")

_SUPPORTED_EXTENSIONS: set[str] = {".csv", ".xlsx", ".xls", ".geojson", ".json", ".h5", ".hdf5"}


def _detect_encoding(path: Path) -> str:
    raw = path.read_bytes()[:1024]
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw[:2] == b"\xff\xfe":
        return "utf-16"
    if raw[:2] == b"\xfe\xff":
        return "utf-16-be"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        try:
            raw.decode("gbk")
            return "gbk"
        except UnicodeDecodeError:
            return "latin-1"


def _build_metadata(path, n_rows, n_cols, columns, dtypes, fmt):
    from datetime import datetime as dt
    return {
        "file": str(path.resolve()),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "format": fmt,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "columns": columns,
        "dtypes": dtypes,
        "loaded_at": dt.now().isoformat(),
    }


def _guess_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext in (".xlsx", ".xls"):
        return "excel"
    if ext in (".geojson", ".json"):
        return "geojson"
    if ext in (".h5", ".hdf5"):
        return "hdf5"
    raise ValueError(f"Unsupported file extension: {ext}")


def _parse_csv(path: Path, **kw) -> tuple:
    encoding = kw.pop("encoding", None) or _detect_encoding(path)
    try:
        df = pd.read_csv(path, encoding=encoding, **kw)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", **kw)
    meta = _build_metadata(path, len(df), len(df.columns), list(df.columns),
                           {c: str(dt) for c, dt in df.dtypes.items()}, "csv")
    meta["encoding"] = encoding
    return df, meta


def _parse_excel(path: Path, **kw) -> tuple:
    sheet = kw.pop("sheet_name", 0)
    df = pd.read_excel(path, sheet_name=sheet, **kw)
    meta = _build_metadata(path, len(df), len(df.columns), list(df.columns),
                           {c: str(dt) for c, dt in df.dtypes.items()}, "excel")
    meta["engine"] = "openpyxl" if path.suffix == ".xlsx" else "xlrd"
    return df, meta


def _parse_geojson(path: Path, **kw) -> tuple:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    if not features:
        return pd.DataFrame(), _build_metadata(path, 0, 0, [], {}, "geojson")
    records = []
    for feat in features:
        props = feat.get("properties", {})
        props["geometry"] = json.dumps(feat.get("geometry", {}))
        records.append(props)
    df = pd.DataFrame(records)
    meta = _build_metadata(path, len(df), len(df.columns), list(df.columns),
                           {c: str(dt) for c, dt in df.dtypes.items()}, "geojson")
    meta["crs"] = data.get("crs", {}).get("properties", {}).get("name", "unknown")
    return df, meta


def _parse_hdf5(path: Path, **kw) -> tuple:
    import h5py
    key = kw.pop("key", None)
    with h5py.File(path, "r") as f:
        if key is None:
            keys = []
            f.visititems(lambda k, v: keys.append(k) if isinstance(v, h5py.Dataset) else None)
            if not keys:
                raise ValueError(f"No datasets found in HDF5 file: {path}")
            key = keys[0]
        data = f[key][()]
    if isinstance(data, np.ndarray):
        if data.ndim == 1:
            df = pd.DataFrame({key: data})
        elif data.ndim == 2:
            df = pd.DataFrame(data, columns=[f"col_{i}" for i in range(data.shape[1])])
        else:
            df = pd.DataFrame({key: data.ravel()})
    else:
        df = pd.DataFrame({key: [data]})
    meta = _build_metadata(path, len(df), len(df.columns), list(df.columns),
                           {c: str(dt) for c, dt in df.dtypes.items()}, "hdf5")
    meta["hdf5_key"] = key
    return df, meta


def load_data(path, fmt=None, **kw):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    fmt = fmt or _guess_format(path)
    kw.pop("format", None)  # Remove 'format' if passed to avoid leaking to pandas
    parsers = {"csv": _parse_csv, "excel": _parse_excel, "geojson": _parse_geojson, "hdf5": _parse_hdf5}
    fn = parsers.get(fmt)
    if fn is None:
        raise ValueError(f"Unsupported format: {fmt}. Supported: {list(parsers.keys())}")
    try:
        df, meta = fn(path, **kw)
        return df, meta
    except Exception as e:
        raise ValueError(f"Failed to parse {path} as {fmt}: {e}") from e


def load_data_dir(dir_path, pattern="*", recursive=False, **kw):
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")
    globber = dir_path.rglob if recursive else dir_path.glob
    results = {}
    for fp in sorted(globber(pattern)):
        if not fp.is_file():
            continue
        try:
            results[fp.name] = load_data(fp, **kw)
        except Exception:
            continue
    return results


__all__ = ["load_data", "load_data_dir"]
