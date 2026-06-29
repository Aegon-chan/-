"""
OpenAI 兼容 API 适配器基类。

DeepSeek、KIMI (Moonshot) 等都使用 OpenAI 兼容的 API 格式，
通过此基类统一实现 chat / stream_chat，减少重复代码。
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI

from backend.models.base import BaseLLM, Message, ModelResponse
from backend.core.exceptions import ConfigError, ModelError

logger = logging.getLogger("research_agent.models")


class OpenAICompatibleLLM(BaseLLM):
    """OpenAI 兼容 API 的 LLM 适配器基类"""

    def __init__(
        self,
        model_id: str,
        api_key: str,
        api_base: str,
        model_name: Optional[str] = None,
    ):
        self.model_id = model_id
        self.model_name = model_name or model_id

        if not api_key or api_key.startswith("your-") or "sk-" not in api_key:
            raise ConfigError(key=f"{model_id}_api_key")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )

    @staticmethod
    def _convert_messages(messages: list[Message]) -> list[dict]:
        """将内部 Message 列表转为 OpenAI API 格式"""
        result = []
        for m in messages:
            entry = {"role": m.role, "content": m.content}
            result.append(entry)
        return result

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ModelResponse:
        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=self._convert_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            logger.error("模型 %s 调用失败: %s", self.model_id, e)
            raise ModelError(model_id=self.model_id, detail=str(e))

        choice = response.choices[0]
        usage = response.usage
        return ModelResponse(
            content=choice.message.content or "",
            model_id=self.model_id,
            token_usage={
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            finish_reason=choice.finish_reason or "",
        )

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self._client.chat.completions.create(
                model=self.model_name,
                messages=self._convert_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
        except Exception as e:
            logger.error("模型 %s 流式调用失败: %s", self.model_id, e)
            raise ModelError(model_id=self.model_id, detail=str(e))

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
