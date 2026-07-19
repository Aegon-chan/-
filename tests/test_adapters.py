"""模型适配器单元测试"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestDeepSeekAdapter:
    """DeepSeek 适配器测试"""

    def test_adapter_rejects_placeholder_key(self):
        """占位符 key 应拒绝注册"""
        from backend.core.exceptions import ConfigError
        from backend.models.adapters.deepseek import DeepSeekAdapter

        with pytest.raises(ConfigError):
            DeepSeekAdapter(api_key="your-deepseek-api-key")

    def test_adapter_rejects_empty_key(self):
        """空 key 应拒绝注册"""
        from backend.core.exceptions import ConfigError
        from backend.models.adapters.deepseek import DeepSeekAdapter

        with pytest.raises(ConfigError):
            DeepSeekAdapter(api_key="")


class TestKimiAdapter:
    """KIMI 适配器测试"""

    def test_adapter_rejects_placeholder_key(self):
        from backend.core.exceptions import ConfigError
        from backend.models.adapters.kimi import KimiAdapter

        with pytest.raises(ConfigError):
            KimiAdapter(api_key="your-kimi-api-key")


class TestModelRegistry:
    """注册表测试"""

    def test_register_and_get(self):
        from backend.models.registry import ModelRegistry

        mock = MagicMock()
        mock.model_id = "test-model"
        ModelRegistry.register_llm("test-model", mock, set_default=True)
        assert ModelRegistry.get_llm("test-model") is mock
        assert ModelRegistry._default_llm == "test-model"
        ModelRegistry.remove_llm("test-model")

    def test_fallback_chain(self):
        from backend.models.registry import ModelRegistry

        mock_a = MagicMock()
        mock_a.model_id = "model-a"
        mock_b = MagicMock()
        mock_b.model_id = "model-b"

        ModelRegistry.register_llm("model-a", mock_a, set_default=True)
        ModelRegistry.register_llm("model-b", mock_b)

        # 指定模型存在 → 返回指定模型
        assert ModelRegistry.get_llm_with_fallback("model-a") is mock_a

        # 指定不存在 → fallback 到默认
        assert ModelRegistry.get_llm_with_fallback("nonexistent") is mock_a

        ModelRegistry.remove_llm("model-a")
        ModelRegistry.remove_llm("model-b")
