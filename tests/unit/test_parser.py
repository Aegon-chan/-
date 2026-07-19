"""Tests for the data format parser module."""
from __future__ import annotations

import pytest
import pandas as pd
from pathlib import Path
from backend.analysis.parser import load_data, load_data_dir


class TestLoadData:
    """Test single-file loading for each supported format."""

    def test_load_csv(self, sample_csv: Path):
        df, meta = load_data(sample_csv)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert len(df.columns) == 3
        assert meta["format"] == "csv"
        assert meta["n_rows"] == 5
        assert meta["n_cols"] == 3
        assert "time" in meta["columns"]
        assert meta["file_name"] == "test_data.csv"

    def test_load_csv_with_explicit_format(self, sample_csv: Path):
        df, meta = load_data(sample_csv, format="csv")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_load_geojson(self, sample_geojson: Path):
        df, meta = load_data(sample_geojson)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert meta["format"] == "geojson"
        assert "name" in df.columns
        assert "geometry" in df.columns
        assert "value" in df.columns

    def test_load_empty_csv(self, empty_csv: Path):
        df, meta = load_data(empty_csv)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert meta["n_rows"] == 0

    def test_load_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_data("/nonexistent/file.csv")

    def test_load_unsupported_format(self, tmp_path: Path):
        path = tmp_path / "test.xyz"
        path.write_text("test", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_data(path)

    def test_load_excel(self, tmp_path: Path):
        df_orig = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        xlsx_path = tmp_path / "test.xlsx"
        df_orig.to_excel(xlsx_path, index=False)
        df, meta = load_data(xlsx_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert meta["format"] == "excel"
        assert list(df.columns) == ["a", "b"]


class TestLoadDataDir:
    """Test directory loading."""

    def test_load_directory(self, tmp_path: Path):
        (tmp_path / "a.csv").write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
        (tmp_path / "b.csv").write_text("x,y\n5,6\n", encoding="utf-8")
        (tmp_path / "note.txt").write_text("hello", encoding="utf-8")

        results = load_data_dir(tmp_path, pattern="*")
        assert len(results) == 2  # skips .txt
        assert "a.csv" in results
        assert "b.csv" in results
        df_a, meta_a = results["a.csv"]
        assert len(df_a) == 2

    def test_load_directory_recursive(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.csv").write_text("x,y\n7,8\n", encoding="utf-8")

        results = load_data_dir(tmp_path, pattern="**/*.csv", recursive=True)
        assert len(results) == 1

    def test_load_nonexistent_dir(self):
        with pytest.raises(NotADirectoryError):
            load_data_dir("/nonexistent_dir")


class TestEncodingDetection:
    """Test automatic encoding detection for CSV files."""

    def test_utf8_encoding(self, tmp_path: Path):
        path = tmp_path / "utf8.csv"
        path.write_text("name,value\n北京,100\n上海,200\n", encoding="utf-8")
        df, meta = load_data(path)
        assert len(df) == 2
        assert df.iloc[0]["name"] == "北京"

    def test_utf8_bom_encoding(self, tmp_path: Path):
        path = tmp_path / "bom.csv"
        data = "name,value\n测试,1\n数据,2\n"
        path.write_bytes(b"\xef\xbb\xbf" + data.encode("utf-8"))
        df, meta = load_data(path)
        assert len(df) == 2
        assert meta["encoding"] == "utf-8-sig"


class TestMetadata:
    """Test metadata correctness."""

    def test_metadata_fields(self, sample_csv: Path):
        _, meta = load_data(sample_csv)
        assert "file" in meta
        assert "file_name" in meta
        assert "file_size_bytes" in meta
        assert "format" in meta
        assert "n_rows" in meta
        assert "n_cols" in meta
        assert "columns" in meta
        assert "dtypes" in meta
        assert "loaded_at" in meta
        assert meta["file_size_bytes"] > 0

    def test_metadata_types(self, sample_csv: Path):
        _, meta = load_data(sample_csv)
        assert isinstance(meta["n_rows"], int)
        assert isinstance(meta["n_cols"], int)
        assert isinstance(meta["columns"], list)
        assert isinstance(meta["dtypes"], dict)
