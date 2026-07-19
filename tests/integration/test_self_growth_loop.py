"""自成长闭环集成测试。

测试 Feedback -> Memory -> Prompt Optimization -> NL2Query 的全链路。
"""
from __future__ import annotations

import pytest
import os


class TestSelfGrowthLoop:
    """Self-growth closed loop integration tests."""

    @pytest.fixture
    def agent(self, tmp_path):
        from backend.core.agent import ResearchAgent
        return ResearchAgent("int_test_session", user_id="int_test_user")

    def test_submit_feedback_creates_memory(self, agent):
        """反馈提交后，MemoryStore 中应出现对应记忆。"""
        agent.submit_feedback(
            message_id="int_msg_1",
            rating=5,
            comment="用户明确偏好彩色图表展示结果",
            tags=["visualization", "color"],
        )
        # 检查记忆库中出现了反馈相关的记忆
        results = agent.search_memories("彩色图表")
        assert len(results) >= 1

    def test_submit_feedback_with_tags_creates_preferences(self, agent):
        """反馈中的标签应创建为偏好类记忆。"""
        agent.submit_feedback(
            message_id="int_msg_2",
            rating=4,
            comment="",
            tags=["折线图", "时序分析"],
        )
        results = agent.list_memories(memory_type="preference", top_k=50)
        pref_keys = [r["key"] for r in results]
        assert any("折线图" in k for k in pref_keys)

    def test_memory_recall_in_chat_context(self, agent):
        """已有的记忆应在对话上下文中被召回。"""
        # 先存入记忆
        agent.memory.add(
            user_id=agent.user_id,
            memory_type="knowledge",
            key="GNSS精度要求",
            value="GNSS形变监测精度需达到毫米级",
            weight=1.0,
        )
        # 模拟记忆召回
        import asyncio
        context = asyncio.run(agent._recall_memories("GNSS精度"))
        assert "GNSS精度要求" in context or "毫米级" in context

    def test_get_optimized_prompt_returns_template(self, agent):
        """get_optimized_prompt 应返回已存储的 prompt 模板内容。"""
        agent.prompt_optimizer.save_template(
            "analysis",
            "你是一个专业的地质形变分析专家。请基于以下数据进行分析：",
        )
        prompt = agent.get_optimized_prompt("analysis")
        assert "地质形变分析专家" in prompt

    def test_get_optimization_stats_contains_all_keys(self, agent):
        """get_optimization_stats 应返回完整的自成长状态信息。"""
        stats = agent.get_optimization_stats()
        assert "user_id" in stats
        assert "memory" in stats
        assert "feedback" in stats
        assert "finetune" in stats
        assert "prompt" in stats
        assert "optimization_enabled" in stats
        assert stats["user_id"] == "int_test_user"

    def test_toggle_optimization(self, agent):
        """切换后台优化开关应返回正确的状态。"""
        enabled = agent.toggle_optimization(enabled=False)
        assert enabled is False
        enabled = agent.toggle_optimization(enabled=True)
        assert enabled is True
        enabled = agent.toggle_optimization()  # 切换
        assert enabled is False

    def test_feedback_weight_delta(self, agent):
        """不同评分的反馈应产生不同的权重调整量。"""
        r1 = agent.submit_feedback("m1", 5, "Excellent")
        r2 = agent.submit_feedback("m2", 1, "Poor")
        assert r1["weight_delta"] > 0  # High rating -> positive delta
        assert r2["weight_delta"] < 0  # Low rating -> negative delta

    def test_memory_optimizer_integration(self, agent):
        """MemoryOptimizer 应能与 MemoryStore 协同工作。"""
        mid = agent.memory.add(
            agent.user_id, "preference", "format_key", "PDF格式偏好",
            weight=1.0,
        )
        # 通过 MemoryOptimizer 计算权重调整
        delta = agent.memory_optimizer.update_weight(feedback_rating=5)
        if delta > 0:
            agent.memory.update_weight(mid, delta)
        updated = agent.memory.get(agent.user_id, memory_type="preference")
        assert any(r["id"] == mid and r["weight"] >= 1.0 for r in updated)

    def test_prompt_versioning(self):
        """Prompt 模板应有版本管理和评分排名。"""
        from backend.self_growth.prompt_optimizer import PromptOptimizer
        import tempfile
        db_path = os.path.join(tempfile.mkdtemp(), "test_prompts_isolated.db")
        opt = PromptOptimizer(db_path=db_path)
        opt.save_template("analysis_prompt_test", "v1 基础分析prompt")
        opt.save_template("analysis_prompt_test", "v2 改进版分析prompt")
        best = opt.get_best_for_task("analysis_prompt_test")
        assert best is not None
        assert best["version"] == 2
        versions = opt.list_versions("analysis_prompt_test")
        assert len(versions) == 2
