"""Tests for PromptOptimizer with APE features."""
from __future__ import annotations

import pytest
from backend.self_growth.prompt_optimizer import PromptOptimizer


class TestPromptOptimizer:
    """Test basic template management."""

    def test_init(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        assert opt is not None

    def test_save_and_get_template(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        v = opt.save_template("analysis", "Analyze the data carefully")
        assert v == 1

        tmpl = opt.get_template("analysis")
        assert tmpl is not None
        assert tmpl["content"] == "Analyze the data carefully"
        assert tmpl["version"] == 1

    def test_get_nonexistent_template(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        assert opt.get_template("nonexistent") is None

    def test_versioning(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        opt.save_template("analysis", "v1 content")
        opt.save_template("analysis", "v2 content", parent_version=1)
        opt.save_template("analysis", "v3 content", parent_version=2)

        versions = opt.list_versions("analysis")
        assert len(versions) == 3
        assert versions[0]["version"] == 3

    def test_get_specific_version(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        opt.save_template("analysis", "v1 content")
        opt.save_template("analysis", "v2 content", parent_version=1)

        tmpl = opt.get_template("analysis", version=1)
        assert tmpl["content"] == "v1 content"


class TestAPE:
    """Test APE search and mutation features."""

    @pytest.mark.asyncio
    async def test_ape_search_basic(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)

        async def eval_fn(prompt):
            return {"score": 0.5}

        result = await opt.ape_search(
            "analysis",
            ["prompt A", "prompt B", "prompt C"],
            eval_fn=eval_fn,
            population_size=3,
            generations=1,
        )
        assert isinstance(result, str)

    def test_regression_check_no_cases(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        result = opt._regression_check("test prompt", "analysis", [])
        assert result["passed"] is True
        assert result["failed_cases"] == []

    def test_regression_check_passes(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        prompt = "Analyze the GNSS displacement data carefully"
        cases = [
            {"input": "test", "expected_output": "GNSS displacement analysis"},
        ]
        result = opt._regression_check(prompt, "analysis", cases)
        assert result["passed"] is True

    def test_regression_check_fails(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        prompt = "Short prompt"
        cases = [
            {"input": "test", "expected_output": "very long expected output with many technical terms that should not all be found"},
        ]
        result = opt._regression_check(prompt, "analysis", cases)
        assert result["passed"] is False
        assert len(result["failed_cases"]) > 0

    @pytest.mark.asyncio
    async def test_ab_test(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)

        async def eval_fn(prompt, inp):
            return {"score": 0.8 if prompt == "prompt B" else 0.6}

        result = await opt.ab_test(
            "analysis",
            "prompt A",
            "prompt B",
            ["input1", "input2"],
            eval_fn=eval_fn,
        )
        assert "winner" in result
        assert "score_a" in result
        assert "score_b" in result
        assert result["improvement"] is not None


class TestGetBestForTask:
    """Test get_best_for_task alias."""

    def test_get_best(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        opt.save_template("analysis", "best content")
        # First version should have score 0.0
        best = opt.get_best_for_task("analysis")
        assert best is not None
        assert best["content"] == "best content"

    def test_get_best_no_template(self, tmp_path):
        db_path = str(tmp_path / "prompts.db")
        opt = PromptOptimizer(db_path=db_path)
        assert opt.get_best_for_task("analysis") is None
