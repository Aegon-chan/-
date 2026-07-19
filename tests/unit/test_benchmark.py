"""Tests for backend/self_growth/benchmark.py"""
from __future__ import annotations

import pytest


class TestFineTuneBenchmark:
    """Test benchmark evaluation"""

    @pytest.fixture
    def benchmark(self):
        from backend.self_growth.benchmark import FineTuneBenchmark
        return FineTuneBenchmark()

    def test_summary_empty(self, benchmark):
        """Summary of unrun benchmark should return a dict"""
        result = benchmark.summary()
        assert result == {"models_evaluated": 0}

    @pytest.mark.asyncio
    async def test_evaluate_model_no_data(self, benchmark):
        """Evaluate model with no data should handle gracefully"""
        result = await benchmark.evaluate_model("base", [])
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_evaluate_base(self, benchmark):
        """_evaluate_base with empty data should return a dict"""
        result = await benchmark._evaluate_base([])
        assert isinstance(result, dict)

    def test_summary_with_results(self, benchmark):
        """Summary should reflect manually set results (list format)"""
        benchmark.results = [
            {
                "model_path": "model-A",
                "improvement": {"accuracy_improvement": 0.05},
            },
        ]
        s = benchmark.summary()
        assert isinstance(s, dict)
        assert s["models_evaluated"] == 1
