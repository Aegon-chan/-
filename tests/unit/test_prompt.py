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