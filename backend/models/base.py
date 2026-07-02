"""
AI 模型接入层抽象接口。

定义统一的 LLM 调用协议，所有模型适配器需实现此接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator


@dataclass
class ContentPart:
    """多模态内容片段"""
    type: str          # "text" | "image_base64"
    text: str = ""
    image_base64: str = ""
    mime_type: str = ""


@dataclass
class Message:
    """对话消息"""
    role: str  # user / assistant / system / tool
    content: str = ""
    multimodal_parts: list[ContentPart] = field(default_factory=list)


@dataclass
class ModelResponse:
    """模型响应"""
    content: str
    model_id: str
    token_usage: dict = field(default_factory=dict)
    finish_reason: str = ""


class BaseLLM(ABC):
    """所有模型适配器的基类。"""

    model_id: str
    api_key: str
    api_base: str

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ModelResponse:
        """同步对话"""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式对话，逐 token 返回"""
        ...


class BaseEmbedding(ABC):
    """嵌入模型基类。"""

    model_id: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转为向量"""
        ...
