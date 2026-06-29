"""记忆权重优化模块"""
from __future__ import annotations


class MemoryOptimizer:
    """基于反馈优化记忆权重"""

    def update_weight(self, feedback_rating: int) -> float:
        delta = {1: 0.1, -1: -0.2, 5: 0.15, 4: 0.05}.get(feedback_rating, 0.0)
        return delta

    def decay(self, weight: float, days: float, half_life: float = 30.0) -> float:
        return weight * (0.5 ** (days / half_life))

    def merge(self, memories: list) -> list:
        return memories
