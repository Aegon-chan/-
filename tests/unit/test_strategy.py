"""Tests for the strategy library."""
from __future__ import annotations

import pytest
from backend.core.strategy import StrategyLibrary


class TestStrategyLibrary:
    @pytest.fixture
    def lib(self, tmp_path):
        db_path = str(tmp_path / "test_strategies.db")
        return StrategyLibrary(db_path=db_path)

    def test_save_and_search(self, lib):
        steps = [{"step": "codegen", "success": True}, {"step": "execute", "success": True}]
        sid = lib.save("analysis", "test query", steps, "success", "gnss", 100.0, "user1")
        assert sid > 0
        results = lib.search("test query", task_type="analysis")
        assert len(results) >= 1
        assert results[0]["task_type"] == "analysis"

    def test_search_by_data_type(self, lib):
        lib.save("analysis", "query1", [], "", "gnss")
        lib.save("analysis", "query2", [], "", "rainfall")
        results = lib.search("", data_type="rainfall")
        assert len(results) == 1

    def test_record_use_success(self, lib):
        sid = lib.save("analysis", "test", [])
        lib.record_use(sid, success=True)
        from sqlite3 import connect
        with connect(str(lib.db_path)) as conn:
            row = conn.execute("SELECT use_count, success_weight FROM strategies WHERE id=?", (sid,)).fetchone()
            assert row[0] == 2

    def test_get_top(self, lib):
        lib.save("analysis", "q1", [], "", "gnss")
        lib.save("analysis", "q2", [], "", "gnss")
        top = lib.get_top("analysis", top_k=10)
        assert len(top) == 2