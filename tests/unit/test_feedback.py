"""Tests for the feedback collection system."""
from __future__ import annotations

import pytest
from backend.self_growth.feedback import FeedbackCollector


class TestFeedbackCollector:
    @pytest.fixture
    def collector(self, tmp_path):
        db_path = str(tmp_path / "test_feedback.db")
        return FeedbackCollector(db_path=db_path)

    def test_collect_feedback(self, collector):
        result = collector.collect(
            message_id="msg1",
            rating=1,
            comment="Great analysis",
            tags=["accurate", "detailed"],
            user_id="user1",
        )
        assert result["message_id"] == "msg1"
        assert result["rating"] == 1

    def test_get_feedback_by_message(self, collector):
        collector.collect("msg1", 1, "good")
        result = collector.get_feedback_by_message("msg1")
        assert result is not None
        assert result["comment"] == "good"

    def test_get_feedback_by_user(self, collector):
        collector.collect("msg1", 1, user_id="user1")
        collector.collect("msg2", -1, user_id="user1")
        results = collector.get_feedback_by_user("user1")
        assert len(results) == 2

    def test_stats(self, collector):
        collector.collect("msg1", 1)
        collector.collect("msg2", -1)
        collector.collect("msg3", 1, comment="nice")
        stats = collector.get_stats()
        assert stats["total"] == 3
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert stats["with_comment"] == 1

    def test_implicit_feedback(self, collector):
        fid = collector.log_implicit("user1", "message_edited", {"old": "a", "new": "b"})
        assert fid > 0
        events = collector.get_implicit_events("user1", "message_edited")
        assert len(events) == 1

    def test_to_training_data(self, collector):
        collector.collect("msg1", 1, comment="good")
        collector.collect("msg2", -1, comment="bad")
        data = collector.to_training_data(min_rating=1)
        assert len(data) == 1

    def test_export_for_finetune(self, collector, tmp_path):
        collector.collect("msg1", 1, comment="good")
        output = str(tmp_path / "train.jsonl")
        count = collector.export_for_finetune(output, min_rating=1)
        assert count == 1
        import os
        assert os.path.exists(output)