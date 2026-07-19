"""Tests for ResearchAgent ReAct loop and chat."""
from __future__ import annotations

import pytest


class TestResearchAgentInit:
    """Test agent initialization."""

    def test_init_minimal(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_session")
        assert agent.session_id == "test_session"
        assert agent.user_id == "default"

    def test_init_with_params(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="s1", model_id="deepseek-chat", user_id="u1")
        assert agent.session_id == "s1"
        assert agent.user_id == "u1"

    def test_property_memory(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="s1")
        mem = agent.memory
        assert mem is not None


class TestResearchAgentFeedback:
    """Test feedback submission and implicit feedback integration."""

    def test_submit_feedback_structure(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_sess")
        result = agent.submit_feedback(
            message_id="msg_1",
            rating=5,
            comment="Great analysis",
            tags=["gnss", "accuracy"],
        )
        assert "feedback_id" in result

    def test_negative_feedback(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_sess")
        result = agent.submit_feedback(
            message_id="msg_2",
            rating=1,
            comment="Wrong result",
            tags=["error"],
        )
        assert "feedback_id" in result


class TestResearchAgentChat:
    """Test chat functionality."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 LLM 环境")
    async def test_chat_basic(self):
        """Test that chat returns a response."""
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_chat")
        response = await agent.chat("Hello")
        assert response is not None
        assert hasattr(response, "content")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 LLM 环境")
    async def test_chat_saves_messages(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_history")
        await agent.chat("Query 1")
        await agent.chat("Query 2")
        assert len(agent.messages) >= 4  # 2 user + 2 assistant


class TestImplicitFeedbackIntegration:
    """Test implicit feedback hook in agent."""

    def test_implicit_feedback_property(self):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_implicit")
        collector = agent.implicit_feedback
        assert collector is not None
        assert collector.enable is True

    def test_implicit_feedback_disabled_via_config(self):
        # Test with env var
        import os
        os.environ["FEATURE_IMPLICIT_FEEDBACK"] = "false"
        try:
            from backend.config import settings
            assert settings.feature_implicit_feedback is False
        except AttributeError:
            pass  # Config may not have the feature flag
        finally:
            os.environ.pop("FEATURE_IMPLICIT_FEEDBACK", None)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 LLM 环境")
    async def test_chat_triggers_implicit_feedback(self):
        """Test that chat triggers implicit feedback recording."""
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="test_trig")
        before = len(agent.implicit_feedback._session_history.get("test_trig", []))
        await agent.chat("Test query for implicit")
        after = len(agent.implicit_feedback._session_history.get("test_trig", []))
        assert after > before
