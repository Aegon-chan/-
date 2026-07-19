"""Tests for backend/models/lora_adapter.py"""
from __future__ import annotations

import pytest


class TestLoRAAdapterLLM:
    """Test LoRA adapter model wrapper"""

    @pytest.fixture
    def config(self):
        return {
            "model_id": "mock-lora-model",
            "base_model_path": "mock-model",
            "adapter_path": "",
            "device": "cpu",
            "max_length": 512,
            "temperature": 0.7,
        }

    def test_init_basic(self, config):
        """Basic initialization"""
        from backend.models.lora_adapter import LoRAAdapterLLM
        model = LoRAAdapterLLM(**config)
        assert model.model_id == "mock-lora-model"
        assert model.device == "cpu"
        assert model.max_length == 512

    def test_init_with_adapter(self, config):
        """Initialization with an adapter path"""
        config["adapter_path"] = "/mock/adapter"
        from backend.models.lora_adapter import LoRAAdapterLLM
        model = LoRAAdapterLLM(**config)
        assert model.adapter_path == "/mock/adapter"

    def test_ensure_loaded_handles_missing(self, config):
        """_ensure_loaded should handle missing base model gracefully"""
        from backend.models.lora_adapter import LoRAAdapterLLM
        model = LoRAAdapterLLM(**config)
        result = model._ensure_loaded()
        assert result is not None  # Should return successfully or raise

    def test_format_messages(self, config):
        """Message formatting should work"""
        from backend.models.base import Message
        from backend.models.lora_adapter import LoRAAdapterLLM
        model = LoRAAdapterLLM(**config)
        messages = [Message(role="user", content="Hello")]
        result = model._format_messages(messages)
        assert isinstance(result, str)
        assert "Hello" in result

    def test_format_messages_empty(self, config):
        """Empty messages should be handled"""
        from backend.models.lora_adapter import LoRAAdapterLLM
        model = LoRAAdapterLLM(**config)
        result = model._format_messages([])
        assert isinstance(result, str)
