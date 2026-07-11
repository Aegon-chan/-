"""Integration test: RAG retrieval -> NL2Query -> Report generation pipeline."""
from __future__ import annotations

import pytest
import asyncio


class TestRAGAnalysisReportPipeline:
    """End-to-end test of the RAG -> Analysis -> Report pipeline."""

    @pytest.fixture
    def agent(self, mock_llm):
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(session_id="int_pipeline", user_id="int_user")
        agent._llm = mock_llm
        return agent

    def test_agent_initialized(self, agent):
        """Agent should initialize with all sub-systems."""
        assert agent.session_id == "int_pipeline"
        assert agent.memory is not None
        assert agent.feedback_collector is not None

    @pytest.mark.asyncio
    async def test_chat_and_feedback_flow(self, agent):
        """Chat then submit feedback - core loop test."""
        response = await agent.chat("分析GNSS监测数据趋势")
        assert response is not None
        assert len(response.content) > 0

        result = agent.submit_feedback(
            message_id="int_msg_1",
            rating=5,
            comment="分析准确，图表清晰",
            tags=["gnss", "accuracy"],
        )
        assert "feedback_id" in result

    def test_memory_creation(self, agent):
        """Ensure memories can be stored and retrieved."""
        agent.memory.add(
            user_id="int_user",
            memory_type="preference",
            key="报告格式",
            value="用户偏好HTML格式的报告",
            weight=0.9,
        )
        result = agent.memory.get("int_user", memory_type="preference")
        assert len(result) >= 1
        assert any("报告格式" in r.get("key", "") for r in result)

    def test_feedback_prompt_optimization(self, agent):
        """Test that feedback triggers optimization flow."""
        from backend.config import settings
        if not settings.feature_self_growth:
            pytest.skip("Self-growth feature disabled")

        result = agent.submit_feedback(
            message_id="int_opt_msg",
            rating=5,
            comment="非常好的分析结果",
            tags=["optimization", "quality"],
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self, agent):
        """Test a simplified pipeline: chat -> memory -> feedback."""
        # Step 1: Chat
        response = await agent.chat("展示降雨量和地下水位相关性")

        # Step 2: Implicit feedback recorded
        signals = agent.implicit_feedback.record_query(
            "int_pipeline", "展示降雨量和地下水位相关性"
        )
        assert isinstance(signals, dict)

        # Step 3: Store explicit feedback
        fb = agent.submit_feedback(
            message_id="int_corr_msg",
            rating=5,
            comment="相关性分析非常有用，图表清晰",
            tags=["correlation", "rainfall", "groundwater"],
        )
        assert fb.get("feedback_id")
