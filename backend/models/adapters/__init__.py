"""AI 模型适配器"""
from __future__ import annotations

from .openai_compat import OpenAICompatibleLLM
from .deepseek import DeepSeekAdapter
from .kimi import KimiAdapter

__all__ = ["OpenAICompatibleLLM", "DeepSeekAdapter", "KimiAdapter"]
