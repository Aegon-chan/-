"""Tests for backend/self_growth/memory_optimizer.py"""
from __future__ import annotations

import pytest


class TestMemoryOptimizer:
    """Test memory optimization functions"""

    @pytest.fixture
    def optimizer(self):
        from backend.self_growth.memory_optimizer import MemoryOptimizer
        return MemoryOptimizer()

    def test_update_weight_positive(self, optimizer):
        """Positive feedback (5) should return positive delta"""
        delta = optimizer.update_weight(5)
        assert delta == 0.2

    def test_update_weight_negative(self, optimizer):
        """Negative feedback (1) should return negative delta"""
        delta = optimizer.update_weight(1)
        assert delta == -0.2

    def test_update_weight_neutral(self, optimizer):
        """Neutral feedback (3) should return zero delta"""
        delta = optimizer.update_weight(3)
        assert delta == 0.0

    def test_decay_recent(self, optimizer):
        """Recent memories should decay less"""
        fresh = optimizer.decay(1.0, 1.0)
        old = optimizer.decay(1.0, 365.0)
        assert fresh > old

    def test_decay_zero_weight(self, optimizer):
        """Zero weight should stay zero"""
        result = optimizer.decay(0.0, 100.0)
        assert result == 0.0

    def test_decay_custom_half_life(self, optimizer):
        """Custom half-life should affect decay rate"""
        fast = optimizer.decay(1.0, 30.0, half_life=7.0)
        slow = optimizer.decay(1.0, 30.0, half_life=365.0)
        assert fast < slow

    def test_update_with_feedback(self, optimizer):
        """Integration of weight update with feedback"""
        result = optimizer.update_with_feedback(0.5, 5, 30.0)
        assert 0 < result <= 5.0

    def test_normalize_weights(self, optimizer):
        """Weight normalization should produce 0-1 range"""
        memories = [
            {"weight": 0.0},
            {"weight": 1.0},
            {"weight": 2.0},
        ]
        result = optimizer.normalize_weights(memories)
        assert len(result) == 3
        nw = [m["weight_normalized"] for m in result]
        assert all(0 <= w <= 1 for w in nw)
        assert nw[2] == 1.0

    def test_normalize_weights_empty(self, optimizer):
        """Empty list should return empty"""
        result = optimizer.normalize_weights([])
        assert result == []

    def test_merge_identical(self, optimizer):
        """Identical memories should merge"""
        memories = [
            {"key": "k1", "value": "v1", "weight": 0.8},
            {"key": "k1", "value": "v1", "weight": 0.6},
        ]
        result = optimizer.merge(memories)
        assert len(result) == 1

    def test_merge_different(self, optimizer):
        """Different memories should stay separate"""
        memories = [
            {"key": "k1", "value": "v1", "weight": 0.8},
            {"key": "k2", "value": "v2", "weight": 0.6},
        ]
        result = optimizer.merge(memories)
        assert len(result) == 2
