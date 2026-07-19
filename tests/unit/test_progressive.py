"""Tests for backend/self_growth/progressive.py"""
from __future__ import annotations

import pytest


class TestProgressiveLearner:
    """Test progressive learning logic"""

    @pytest.fixture
    def learner(self):
        from backend.self_growth.progressive import ProgressiveLearner
        return ProgressiveLearner()

    def test_record_and_get_stats(self, learner):
        """Recording tasks should make stats accessible"""
        learner.record_task("analysis", 100.0, success=True)
        stats = learner.get_task_stats("analysis")
        assert stats is not None
        assert stats["count"] >= 1

    def test_record_failure(self, learner):
        """Failure should be tracked separately"""
        learner.record_task("analysis", 200.0, success=False)
        stats = learner.get_task_stats("analysis")
        assert stats is not None

    def test_get_stats_nonexistent(self, learner):
        """Getting stats for unseen type should return empty"""
        stats = learner.get_task_stats("nonexistent")
        assert stats == {"count": 0}

    def test_record_multiple(self, learner):
        """Multiple recordings of same type should accumulate"""
        for _ in range(5):
            learner.record_task("search", 50.0, success=True)
        stats = learner.get_task_stats("search")
        assert stats["count"] == 5

    def test_reset(self, learner):
        """Reset should clear all recorded data"""
        learner.record_task("analysis", 100.0)
        learner.reset()
        stats = learner.get_task_stats("analysis")
        assert stats == {"count": 0}

    def test_trend_analysis(self, learner):
        """Analyze trend with improving data"""
        for i in range(5):
            learner.record_task("analysis", 100.0 - i * 10, success=True)
        stats = learner.get_task_stats("analysis")
        assert stats is not None
        assert isinstance(stats["avg_duration_ms"], (int, float))

    def test_analyze_improving(self, learner):
        """_is_improving should check for downward trend"""
        for ms in [200, 180, 150, 120, 100]:
            learner.record_task("optimizing", ms, success=True)
        stats = learner.get_task_stats("optimizing")
        assert stats is not None
        assert "learning_progress" in stats
