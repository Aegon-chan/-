"""Tests for the prompt optimizer."""
from __future__ import annotations

import pytest
from backend.self_growth.prompt_optimizer import PromptOptimizer


class TestPromptOptimizer:
    @pytest.fixture
    def opt(self, tmp_path):
        db_path = str(tmp_path / "test_prompts.db")
        return PromptOptimizer(db_path=db_path)

    def test_save_and_get_template(self, opt):
        opt.save_template("analysis", "You are an expert analyst.")
        tpl = opt.get_template("analysis")
        assert tpl is not None
        assert "expert" in tpl["content"]
        assert tpl["version"] == 1

    def test_version_increment(self, opt):
        opt.save_template("analysis", "v1")
        opt.save_template("analysis", "v2")
        tpl = opt.get_template("analysis", version=2)
        assert tpl["version"] == 2
        assert tpl["content"] == "v2"

    def test_list_versions(self, opt):
        opt.save_template("analysis", "v1")
        opt.save_template("analysis", "v2")
        versions = opt.list_versions("analysis")
        assert len(versions) == 2

    async def test_optimize_without_feedback(self, opt):
        opt.save_template("analysis", "default prompt")
        result = await opt.optimize("analysis", [])
        assert result == "default prompt"

    async def test_optimize_empty_feedback(self, opt):
        opt.save_template("analysis", "default_prompt")
        result = await opt.optimize("analysis", [{"rating": 1, "comment": "good"}])
        assert result is not None
class TestPromptOptimizerExtensions:
    """PromptOptimizer 新 API 测试。"""

    @pytest.fixture
    def opt(self, tmp_path):
        from backend.self_growth.prompt_optimizer import PromptOptimizer
        db_path = str(tmp_path / "test_prompts_ext.db")
        return PromptOptimizer(db_path=db_path)

    def test_get_best_for_task_returns_best(self, opt):
        opt.save_template("analysis", "v1_content")
        opt.save_template("analysis", "v2_better")
        best = opt.get_best_for_task("analysis")
        assert best is not None
        assert best["version"] == 2
        assert best["content"] == "v2_better"

    def test_get_best_for_task_no_templates(self, opt):
        best = opt.get_best_for_task("nonexistent_type")
        assert best is None

    def test_get_best_for_task_returns_dict(self, opt):
        opt.save_template("report", "daily report template")
        best = opt.get_best_for_task("report")
        assert isinstance(best, dict)
        assert "task_type" in best
        assert "content" in best
        assert "version" in best

    async def test_auto_optimize_low_rating_skips(self, opt):
        opt.save_template("analysis", "standard analysis prompt")
        result = await opt.auto_optimize(
            "analysis",
            {"comment": "not good", "rating": 2},
            rating=2,
        )
        assert result is None  # Should skip for low rating

    async def test_auto_optimize_high_rating_attempts(self, opt):
        opt.save_template("analysis", "standard analysis prompt")
        # With high rating, should try to optimize (may use LLM fallback)
        result = await opt.auto_optimize(
            "analysis",
            {"comment": "Great analysis!", "rating": 5},
            rating=5,
        )
        # Even if no LLM available, should not raise
        assert result is not None  # Without LLM, returns current template content

