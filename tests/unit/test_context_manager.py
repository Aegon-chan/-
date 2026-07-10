"""Tests for backend.core.context_manager."""

from __future__ import annotations

from backend.core.context_manager import (
    CHARS_PER_TOKEN,
    ContextManager,
    _format_summary_prompt,
    count_messages_tokens,
    count_rounds,
    estimate_tokens,
)
from backend.models.base import Message


def _msg(role: str, content: str) -> Message:
    """Shortcut to create a Message."""
    return Message(role=role, content=content)


class TestEstimateTokens:
    def test_estimate_empty(self) -> None:
        assert estimate_tokens("") == 0

    def test_estimate_short(self) -> None:
        assert estimate_tokens("hello") >= 1

    def test_estimate_chinese(self) -> None:
        text = "你好世界" * 50
        expected = max(1, int(len(text) / CHARS_PER_TOKEN))
        assert estimate_tokens(text) == expected

    def test_estimate_none(self) -> None:
        assert estimate_tokens(None) == 0


class TestCountMessagesTokens:
    def test_empty_list(self) -> None:
        assert count_messages_tokens([]) == 0

    def test_single_message(self) -> None:
        msgs = [_msg("user", "hello")]
        assert count_messages_tokens(msgs) == estimate_tokens("hello")

    def test_multiple_messages(self) -> None:
        msgs = [
            _msg("system", "You are a helpful assistant."),
            _msg("user", "Hi there"),
            _msg("assistant", "Hello! How can I help?"),
        ]
        expected = sum(estimate_tokens(m.content) for m in msgs)
        assert count_messages_tokens(msgs) == expected


class TestCountRounds:
    def test_empty(self) -> None:
        assert count_rounds([]) == 0

    def test_system_only(self) -> None:
        msgs = [_msg("system", "prompt")]
        assert count_rounds(msgs) == 0

    def test_one_round(self) -> None:
        msgs = [
            _msg("user", "hi"),
            _msg("assistant", "hello"),
        ]
        assert count_rounds(msgs) == 1

    def test_two_rounds(self) -> None:
        msgs = [
            _msg("user", "q1"),
            _msg("assistant", "a1"),
            _msg("user", "q2"),
            _msg("assistant", "a2"),
        ]
        assert count_rounds(msgs) == 2

    def test_with_system_messages(self) -> None:
        msgs = [
            _msg("system", "prompt"),
            _msg("user", "q1"),
            _msg("assistant", "a1"),
            _msg("system", "context"),
            _msg("user", "q2"),
            _msg("assistant", "a2"),
        ]
        assert count_rounds(msgs) == 2

    def test_unbalanced(self) -> None:
        msgs = [
            _msg("user", "q1"),
            _msg("assistant", "a1"),
            _msg("user", "q2"),
        ]
        assert count_rounds(msgs) == 1


class TestFormatSummaryPrompt:
    def test_basic(self) -> None:
        msgs = [
            _msg("user", "请分析GNSS数据"),
            _msg("assistant", "正在分析您的数据..."),
        ]
        result = _format_summary_prompt(msgs)
        assert "用户" in result
        assert "助手" in result
        assert "GNSS" in result

    def test_empty(self) -> None:
        result = _format_summary_prompt([])
        assert "对话历史" in result


class TestContextManagerInit:
    def test_defaults(self) -> None:
        cm = ContextManager()
        assert cm.max_rounds == 30
        assert cm.max_tokens == 12000
        assert cm.reserve_recent_rounds == 10
        assert cm.strategy == "truncate"
        assert cm.enabled is True

    def test_custom_params(self) -> None:
        cm = ContextManager(max_rounds=10, max_tokens=500, reserve_recent_rounds=3, strategy="summarize", enabled=False)
        assert cm.max_rounds == 10
        assert cm.max_tokens == 500
        assert cm.reserve_recent_rounds == 3
        assert cm.strategy == "summarize"
        assert cm.enabled is False


class TestContextManagerTrim:
    def test_disabled_returns_unchanged(self) -> None:
        cm = ContextManager(enabled=False, max_rounds=1)
        msgs = [_msg("user", "q1"), _msg("assistant", "a1"),
                _msg("user", "q2"), _msg("assistant", "a2")]
        result = cm.trim_context(msgs)
        assert len(result) == 4

    def test_empty_messages(self) -> None:
        cm = ContextManager()
        assert cm.trim_context([]) == []

    def test_within_limits_no_trim(self) -> None:
        cm = ContextManager(max_rounds=10, max_tokens=100000)
        msgs = [_msg("user", "hi"), _msg("assistant", "hello")]
        result = cm.trim_context(msgs)
        assert len(result) == 2

    def test_truncate_on_token_limit(self) -> None:
        cm = ContextManager(max_rounds=100, max_tokens=3, reserve_recent_rounds=1)
        msgs = [
            _msg("user", "a" * 100),
            _msg("assistant", "b" * 100),
            _msg("user", "c"),
            _msg("assistant", "d"),
        ]
        result = cm.trim_context(msgs)
        assert len(result) <= len(msgs)
        assert any(m.content == "c" for m in result)
        assert any(m.content == "d" for m in result)

    def test_truncate_on_round_limit(self) -> None:
        cm = ContextManager(max_rounds=2, max_tokens=100000, reserve_recent_rounds=1)
        msgs = [
            _msg("user", "q1"), _msg("assistant", "a1"),
            _msg("user", "q2"), _msg("assistant", "a2"),
            _msg("user", "q3"), _msg("assistant", "a3"),
        ]
        result = cm.trim_context(msgs)
        conv = [m for m in result if m.role != "system"]
        assert len(conv) == 2
        assert conv[0].content == "q3"
        assert conv[1].content == "a3"

    def test_preserves_last_system_message(self) -> None:
        cm = ContextManager(max_rounds=1, reserve_recent_rounds=1)
        msgs = [
            _msg("system", "current_prompt"),
            _msg("user", "old_q"),
            _msg("assistant", "old_a"),
            _msg("user", "new_q"),
            _msg("assistant", "new_a"),
        ]
        result = cm.trim_context(msgs)
        system_msgs = [m for m in result if m.role == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0].content == "current_prompt"

    def test_summarize_strategy(self) -> None:
        cm = ContextManager(max_rounds=2, reserve_recent_rounds=1, strategy="summarize")
        msgs = [
            _msg("system", "prompt"),
            _msg("user", "q1"), _msg("assistant", "a1"),
            _msg("user", "q2"), _msg("assistant", "a2"),
            _msg("user", "q3"), _msg("assistant", "a3"),
        ]
        result = cm.trim_context(msgs)
        system_msgs = [m for m in result if m.role == "system"]
        conv = [m for m in result if m.role != "system"]
        assert len(system_msgs) >= 1
        assert len(conv) == 2
        assert conv[0].content == "q3"
        assert cm.get_summary() != "" or any("历史" in m.content for m in system_msgs)


class TestContextManagerStatsAndConfig:
    def test_get_stats_default(self) -> None:
        cm = ContextManager()
        stats = cm.get_stats()
        assert stats["enabled"] is True
        assert stats["strategy"] == "truncate"
        assert stats["max_rounds"] == 30
        assert stats["max_tokens"] == 12000
        assert stats["reserve_recent_rounds"] == 10
        assert stats["trim_count"] == 0
        assert stats["has_summary"] is False

    def test_stats_after_trim(self) -> None:
        cm = ContextManager(max_rounds=1, reserve_recent_rounds=1)
        msgs = [
            _msg("user", "q1"), _msg("assistant", "a1"),
            _msg("user", "q2"), _msg("assistant", "a2"),
        ]
        cm.trim_context(msgs)
        stats = cm.get_stats()
        assert stats["trim_count"] == 1
        assert stats["last_trimmed_rounds"] == 2

    def test_to_config_excludes_runtime(self) -> None:
        cm = ContextManager()
        config = cm.to_config()
        assert "trim_count" not in config
        assert "last_trimmed_rounds" not in config
        assert config["max_rounds"] == 30

    def test_update_and_get_summary(self) -> None:
        cm = ContextManager()
        assert cm.get_summary() == ""
        cm.update_summary("test summary")
        assert cm.get_summary() == "test summary"
        stats = cm.get_stats()
        assert stats["has_summary"] is True

    def test_summarize_with_existing_summary(self) -> None:
        cm = ContextManager(max_rounds=2, reserve_recent_rounds=1, strategy="summarize")
        cm.update_summary("previous summary")
        msgs = [
            _msg("user", "q1"), _msg("assistant", "a1"),
            _msg("user", "q2"), _msg("assistant", "a2"),
            _msg("user", "q3"), _msg("assistant", "a3"),
        ]
        result = cm.trim_context(msgs)
        conv = [m for m in result if m.role != "system"]
        assert len(conv) == 2
        assert conv[0].content == "q3"
