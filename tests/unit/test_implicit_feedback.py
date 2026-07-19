"""Tests for ImplicitFeedbackCollector."""
from __future__ import annotations

from backend.self_growth.implicit_feedback import ImplicitFeedbackCollector


class TestImplicitFeedbackCollector:
    """Test implicit feedback detection and storage."""

    def test_init(self):
        collector = ImplicitFeedbackCollector()
        assert collector is not None
        assert collector.enable is True

    def test_disabled(self):
        collector = ImplicitFeedbackCollector(enable=False)
        result = collector.record_query("session_1", "test query")
        assert result == {}

    def test_first_query_no_signals(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        signals = collector.record_query("session_1", "分析GNSS数据")
        assert len(signals) == 0  # First query, no signals expected

    def test_repeated_query_detection(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(
            db_path=db_path, similarity_threshold=0.8
        )
        collector.record_query("session_1", "test query")
        signals = collector.record_query("session_1", "test query")
        assert "repeated_query" in signals

    def test_rapid_requery_detection(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(
            db_path=db_path, topic_switch_window_s=30
        )
        collector.record_query("session_1", "分析GNSS数据")
        # Rapidly ask a similar query
        signals = collector.record_query("session_1", "分析GNSS位移趋势")
        # Should detect either rapid_requery or topic_switch depending on similarity
        has_signal = "rapid_requery" in signals or "topic_switch" in signals
        assert has_signal

    def test_record_edit(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        signal = collector.record_edit("session_1", "分析GNSS", "分析GNSS详细数据")
        assert "edit" in signal
        assert signal["edit"]["change_type"] in ("minor", "major")

    def test_record_identical_edit(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        signal = collector.record_edit("session_1", "相同文本", "相同文本")
        assert signal == {}  # No signal for identical text

    def test_get_session_signals(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        collector.record_query("session_1", "查询A")
        collector.record_query("session_1", "查询A")  # Repeated
        collector.record_edit("session_1", "原文本", "编辑后文本")

        stats = collector.get_session_signals("session_1")
        assert stats["query_count"] == 2
        assert stats["repeated_queries"] >= 0

    def test_get_session_summary(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        collector.record_query("session_1", "查询A")
        summary = collector.get_session_summary("session_1")
        assert summary["session_id"] == "session_1"
        assert summary["total_queries"] >= 1

    def test_reset_session(self, tmp_path):
        db_path = str(tmp_path / "feedback.db")
        collector = ImplicitFeedbackCollector(db_path=db_path)
        collector.record_query("session_1", "查询A")
        collector.reset_session("session_1")
        stats = collector.get_session_signals("session_1")
        assert stats.get("query_count", 0) == 0

    def test_set_enabled(self, tmp_path):
        collector = ImplicitFeedbackCollector()
        assert collector.enable is True
        collector.set_enabled(False)
        assert collector.enable is False
