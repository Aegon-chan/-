"""Tests for the memory system."""
from __future__ import annotations

import pytest
from backend.core.memory import MemoryStore


class TestMemoryStore:
    @pytest.fixture
    def store(self, tmp_path):
        db_path = str(tmp_path / "test_memory.db")
        return MemoryStore(db_path=db_path)

    def test_add_and_get(self, store):
        mid = store.add("user1", "preference", "report_format", "Word format")
        assert mid > 0
        results = store.get("user1", memory_type="preference")
        assert len(results) == 1
        assert results[0]["key"] == "report_format"

    def test_add_duplicate_key(self, store):
        store.add("user1", "preference", "key1", "value1", weight=1.0)
        mid2 = store.add("user1", "preference", "key1", "value1_updated", weight=0.5)
        results = store.get("user1", memory_type="preference")
        assert len(results) == 1
        assert results[0]["weight"] > 1.0
        assert "updated" in results[0]["value"]

    def test_search(self, store):
        store.add("user1", "knowledge", "GNSS accuracy", "mm level")
        store.add("user1", "knowledge", "InSAR wavelength", "C-band 5.6cm")
        results = store.search("user1", "GNSS")
        assert len(results) >= 1
        assert any("GNSS" in r["key"] for r in results)

    def test_weight_decay(self, store):
        store.add("user1", "experience", "test_key", "test_value", weight=1.0)
        store.decay_weights(factor=0.5)
        results = store.get("user1")
        assert len(results) == 0 or results[0]["weight"] < 1.0

    def test_update_weight(self, store):
        mid = store.add("user1", "preference", "key", "val", weight=1.0)
        store.update_weight(mid, 0.5)
        results = store.get("user1")
        assert results[0]["weight"] == 1.5

    def test_delete(self, store):
        mid = store.add("user1", "preference", "key", "val")
        store.delete(mid)
        results = store.get("user1")
        assert len(results) == 0

    def test_stats(self, store):
        store.add("user1", "preference", "a", "1")
        store.add("user1", "knowledge", "b", "2")
        stats = store.get_stats("user1")
        assert stats["total"] == 2
        assert "preference" in stats["by_type"]
        assert "knowledge" in stats["by_type"]