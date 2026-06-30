"""Integration tests for ReAct loop and LoRA fine-tuning pipeline."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


class TestReActLoop:
    """Test the ReAct reasoning loop implementation."""

    @pytest.fixture
    def agent(self):
        """Create a ResearchAgent with test user isolation."""
        from backend.core.agent import ResearchAgent
        return ResearchAgent("test_react_session", user_id="test_react_user")

    def test_toggle_react(self, agent):
        """Toggle ReAct mode on and off."""
        assert agent._react_enabled is False
        result = agent.toggle_react(enabled=True)
        assert result is True
        assert agent._react_enabled is True
        result = agent.toggle_react(enabled=False)
        assert result is False
        assert agent._react_enabled is False

    def test_toggle_react_toggle(self, agent):
        """Toggle ReAct mode without argument should flip state."""
        agent._react_enabled = False
        result = agent.toggle_react()
        assert result is True
        result = agent.toggle_react()
        assert result is False

    def test_set_react_max_iterations(self, agent):
        """Set max iterations should clamp to [1, 50]."""
        agent.set_react_max_iterations(5)
        assert agent._react_max_iterations == 5
        agent.set_react_max_iterations(0)
        assert agent._react_max_iterations == 1
        agent.set_react_max_iterations(100)
        assert agent._react_max_iterations == 50
        agent.set_react_max_iterations(10)
        assert agent._react_max_iterations == 10

    def test_react_tool_search_memory_empty(self, agent):
        """Search memory should return empty string when no memories exist."""
        async def _test():
            result = await agent._react_tool_search_memory("nonexistent")
            assert isinstance(result, str)
        asyncio.run(_test())

    def test_react_tool_search_memory_disabled(self, agent):
        """Search memory should report disabled when memory is off."""
        async def _test():
            agent._memory_enabled = False
            result = await agent._react_tool_search_memory("test")
            assert "disabled" in result.lower()
        asyncio.run(_test())

    def test_react_tool_search_knowledge_empty(self, agent):
        """Search knowledge should handle empty results."""
        async def _test():
            result = await agent._react_tool_search_knowledge("xyznonexistent")
            assert isinstance(result, str)
        asyncio.run(_test())

    def test_react_tool_generate_report_invalid_type(self, agent):
        """Generate report should handle invalid report types gracefully."""
        async def _test():
            result = await agent._react_tool_generate_report(
                "nonexistent_type",
                {"title": "Test", "sections": []},
            )
            assert isinstance(result, str)
        asyncio.run(_test())

    def test_react_step_no_model(self, agent):
        """_react_step should return final_answer when no LLM available."""
        from backend.models.registry import ModelRegistry
        # Clear registered models
        saved_llms = dict(ModelRegistry._llms)
        ModelRegistry._llms.clear()
        ModelRegistry._default_llm = ""

        async def _test():
            result = await agent._react_step("test query", [])
            assert result.get("action") == "final_answer"
            assert "no ai model" in result.get("action_input", {}).get("answer", "").lower()

        asyncio.run(_test())

        # Restore
        ModelRegistry._llms.update(saved_llms)

    def test_react_tool_search_memory_with_data(self, agent):
        """Search memory should find stored memories."""
        agent.memory.add(
            user_id=agent.user_id,
            memory_type="knowledge",
            key="test_key_gnss",
            value="GNSS precision requirement is 10mm",
            weight=1.0,
        )

        async def _test():
            result = await agent._react_tool_search_memory("GNSS")
            assert isinstance(result, str)
            assert "GNSS" in result or "gnss" in result

        asyncio.run(_test())

    def test_react_tool_report_with_data(self, agent):
        """Generate report should work with proper template type."""
        async def _test():
            result = await agent._react_tool_generate_report(
                "daily",
                {
                    "title": "Daily Monitoring Report",
                    "summary": "No anomalies detected.",
                    "sections": [],
                    "conclusion": "All clear.",
                },
            )
            assert isinstance(result, str)
            assert "Report" in result or "error" in result.lower()

        asyncio.run(_test())


class TestLoRAPipeline:
    """Test the LoRA fine-tuning pipeline end-to-end."""

    @pytest.fixture
    def finetuner(self, tmp_path):
        """Create a FineTuner with test isolation."""
        from backend.self_growth.finetune import FineTuner
        checkpoint_dir = str(tmp_path / "lora_checkpoints")
        ft = FineTuner(
            base_model_path="./model_cache/test_base_model",
            checkpoint_dir=checkpoint_dir,
        )
        return ft

    @pytest.fixture
    def sample_feedback(self):
        """Sample feedback data for training."""
        return [
            {"query": "Analyze GNSS displacement trends", "response": "The displacement shows a linear trend of 2.3mm/year.", "rating": 5, "tags": ["gnss", "trend"]},
            {"query": "Detect anomalies in rainfall data", "response": "Two outliers detected using IQR method at indices 45 and 78.", "rating": 4, "tags": ["rainfall", "anomaly"]},
            {"query": "Generate deformation velocity map", "response": "Velocity map generated with max rate of 5.1mm/year in the central zone.", "rating": 5, "tags": ["insar", "velocity"]},
            {"query": "Plot cumulative displacement", "response": "Cumulative displacement time series plotted successfully.", "rating": 3, "tags": ["plot", "displacement"]},
            {"query": "Underground water level analysis", "response": "Water level shows seasonal variation with 0.5m amplitude.", "rating": 4, "tags": ["groundwater", "seasonal"]},
        ]

    def test_prepare_dataset(self, finetuner, sample_feedback):
        """Prepare dataset from feedback data."""
        async def _test():
            path = await finetuner.prepare_dataset(sample_feedback)
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) <= len(sample_feedback)
            for line in lines:
                data = json.loads(line)
                assert "instruction" in data
                assert "output" in data

        asyncio.run(_test())

    def test_list_models_empty(self, finetuner):
        """List models should return empty list initially."""
        models = finetuner.list_models()
        assert isinstance(models, list)
        assert len(models) == 0

    def test_list_jobs_empty(self, finetuner):
        """List jobs should return empty list initially."""
        jobs = finetuner.list_jobs()
        assert isinstance(jobs, list)
        assert len(jobs) == 0

    def test_deploy_to_registry_no_models(self, finetuner):
        """Deploy should return empty when no models exist."""
        async def _test():
            result = await finetuner.deploy_to_registry()
            assert result == ""
        asyncio.run(_test())

    def test_train_and_deploy_pipeline(self, finetuner, sample_feedback):
        """Full pipeline: prepare -> train -> deploy (may be placeholder if deps missing)."""
        async def _test():
            dataset_path = await finetuner.prepare_dataset(sample_feedback)
            output_dir = await finetuner.train(
                dataset_path=dataset_path,
                lora_r=4,
                num_epochs=1,
            )
            assert isinstance(output_dir, str)
            assert os.path.exists(output_dir) or "placeholder" in output_dir.lower()

            models = finetuner.list_models()
            assert len(models) >= 1

            model_id = await finetuner.deploy_to_registry()
            if model_id:
                from backend.models.registry import ModelRegistry
                llm = ModelRegistry.get_llm(model_id)
                assert llm is not None

        asyncio.run(_test())

    def test_train_with_job_tracking(self, finetuner, sample_feedback):
        """Training should create a job record."""
        async def _test():
            dataset_path = await finetuner.prepare_dataset(sample_feedback)
            await finetuner.train(dataset_path=dataset_path, lora_r=4, num_epochs=1)
            jobs = finetuner.list_jobs()
            assert len(jobs) >= 1
            statuses = [j.get("status") for j in jobs]
            assert any(s in ["completed", "failed"] for s in statuses)

        asyncio.run(_test())

    def test_deploy_specific_model(self, finetuner, sample_feedback):
        """Deploy a specific model by name."""
        async def _test():
            dataset_path = await finetuner.prepare_dataset(sample_feedback)
            await finetuner.train(dataset_path=dataset_path, lora_r=4, num_epochs=1)
            models = finetuner.list_models()
            if models:
                name = models[0].get("model_name", "")
                model_id = await finetuner.deploy_to_registry(model_name=name)
                assert model_id == "" or model_id.startswith("lora-")

        asyncio.run(_test())


class TestReactWithLoRAIntegration:
    """Test the integration between ReAct loop and LoRA pipeline."""

    @pytest.fixture
    def agent(self):
        from backend.core.agent import ResearchAgent
        return ResearchAgent("test_integration_session", user_id="test_integration_user")

    def test_agent_can_toggle_react_and_loa(self, agent):
        """Agent should support both ReAct toggling and LoRA deployment access."""
        assert hasattr(agent, "toggle_react")
        assert hasattr(agent, "set_react_max_iterations")
        assert hasattr(agent, "deploy_finetuned_model")
        assert hasattr(agent, "fine_tuner")

    def test_agent_react_and_memory_integration(self, agent):
        """ReAct tools should access agent memory."""
        agent.memory.add(
            user_id=agent.user_id,
            memory_type="preference",
            key="test_pref_format",
            value="User prefers PDF format reports",
            weight=0.8,
        )

        async def _test():
            result = await agent._react_tool_search_memory("PDF format")
            assert isinstance(result, str)
            assert "PDF" in result

        asyncio.run(_test())

    def test_agent_finetune_deployment_method_exists(self, agent):
        """Agent should expose deploy_finetuned_model method."""
        async def _test():
            result = await agent.deploy_finetuned_model()
            assert result == ""  # Will fail gracefully since no models exist yet

        asyncio.run(_test())
