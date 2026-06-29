"""反馈收集与处理模块"""
from __future__ import annotations


class FeedbackCollector:
    """用户反馈收集器"""

    async def collect(self, message_id: str, rating: int, comment: str = "",
                      tags: list = None) -> dict:
        return {"collected": True, "message_id": message_id, "rating": rating}

    async def to_training_data(self, min_rating: int = 4) -> list:
        return []
