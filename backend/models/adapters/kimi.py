"""KIMI (Moonshot) 模型适配器"""
from __future__ import annotations

from backend.models.adapters.openai_compat import OpenAICompatibleLLM


class KimiAdapter(OpenAICompatibleLLM):
    """KIMI (Moonshot) 适配器 (moonshot-v1)

    通过 Moonshot API 接入 KIMI 模型。
    API 文档: https://platform.moonshot.cn/docs
    """

    def __init__(self, api_key: str, api_base: str = "https://api.moonshot.cn"):
        super().__init__(
            model_id="moonshot-v1",
            api_key=api_key,
            api_base=api_base,
            model_name="moonshot-v1",
        )
