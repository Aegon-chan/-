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
        store.add("user1", "preference", "key1", "value1_updated", weight=0.5)
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
class TestMemoryStoreFeedback:
    """MemoryStore feedback integration tests."""

    @pytest.fixture
    def store(self, tmp_path):
        from backend.core.memory import MemoryStore
        db_path = str(tmp_path / "test_feedback_memory.db")
        return MemoryStore(db_path=db_path)

    def test_store_feedback_memory_with_comment(self, store):
        feedback = {"comment": "User prefers line charts", "tags": [], "rating": 4, "content": ""}
        ids = store.store_feedback_memory("user1", feedback)
        assert len(ids) > 0
        results = store.get("user1", memory_type="knowledge")
        assert any("line charts" in r["value"] for r in results)

    def test_store_feedback_memory_with_tags(self, store):
        feedback = {"comment": "", "tags": ["rainfall", "correlation"], "rating": 5, "content": ""}
        ids = store.store_feedback_memory("user1", feedback)
        assert len(ids) >= 2  # one per tag
        results = store.get("user1", memory_type="preference")
        assert any("rainfall" in r["key"] for r in results)
        assert any("correlation" in r["key"] for r in results)

    def test_store_feedback_memory_empty(self, store):
        feedback = {"comment": "", "tags": [], "rating": 3, "content": ""}
        ids = store.store_feedback_memory("user1", feedback)
        assert len(ids) == 0

    def test_store_feedback_memory_high_rating(self, store):
        feedback = {"comment": "Great tool", "tags": [], "rating": 5, "content": "Excellent results"}
        ids = store.store_feedback_memory("user1", feedback)
        assert len(ids) >= 2  # knowledge + experience
        results = store.get("user1", memory_type="experience")
        assert any("Excellent results" in r["value"] for r in results)

    def test_get_relevant_combines_search_and_type(self, store):
        store.add("user1", "preference", "pref_key", "pref_val", weight=1.0)
        store.add("user1", "knowledge", "know_key", "know_val", weight=0.8)
        results = store.get_relevant("user1", "pref", memory_types=["preference", "knowledge"])
        assert len(results) >= 1
        assert any(r["key"] == "pref_key" for r in results)

    def test_get_relevant_dedup(self, store):
        store.add("user1", "preference", "dup_key", "dup_val", weight=1.0)
        store.add("user1", "knowledge", "dup_key", "dup_val", weight=0.9)
        results = store.get_relevant("user1", "dup", memory_types=["preference", "knowledge"])
        keys = [r["key"] for r in results]
        assert keys.count("dup_key") == 1

    def test_get_relevant_sorted_by_weight(self, store):
        store.add("user1", "preference", "high", "high_val", weight=0.9)
        store.add("user1", "knowledge", "low", "low_val", weight=0.1)
        store.add("user1", "preference", "mid", "mid_val", weight=0.5)
        results = store.get_relevant("user1", "val", memory_types=None)
        if len(results) >= 3:
            assert results[0]["weight"] >= results[-1]["weight"]

