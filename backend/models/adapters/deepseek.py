"""DeepSeek 模型适配器"""
from __future__ import annotations

from backend.models.adapters.openai_compat import OpenAICompatibleLLM


class DeepSeekAdapter(OpenAICompatibleLLM):
    """DeepSeek 适配器 (deepseek-chat)

    通过 OpenAI 兼容的 API 接入 DeepSeek 模型。
    API 文档: https://api-docs.deepseek.com/
    """

    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com"):
        super().__init__(
            model_id="deepseek-chat",
            api_key=api_key,
            api_base=api_base,
            model_name="deepseek-chat",
        )
