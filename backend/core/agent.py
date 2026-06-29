"""
智能体核心引擎。

协调多模型调用、知识检索、数据分析、记忆管理和自我成长。
采用 ReAct（Reasoning + Acting）模式执行任务。
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from backend.models.base import BaseLLM, Message, ModelResponse
from backend.models.registry import ModelRegistry


class ResearchAgent:
    """科研数据分析智能体"""

    def __init__(self, session_id: str, model_id: Optional[str] = None):
        self.session_id = session_id
        self.model_id = model_id or ModelRegistry._default_llm
        self.messages: list[Message] = []
        self._llm: Optional[BaseLLM] = None

    async def _get_llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = ModelRegistry.get_llm(self.model_id)
            if self._llm is None:
                raise ValueError(f"模型 {self.model_id} 未注册")
        return self._llm

    async def chat(self, user_input: str) -> ModelResponse:
        """执行一次对话"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        context = await self._retrieve_context(user_input)
        if context:
            self.messages.append(Message(role="system", content=f"[相关背景]\n{context}"))
        response = await llm.chat(self.messages)
        self.messages.append(response)
        return response

    async def stream_chat(self, user_input: str) -> AsyncIterator[str]:
        """流式对话"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        context = await self._retrieve_context(user_input)
        if context:
            self.messages.append(Message(role="system", content=f"[相关背景]\n{context}"))
        full_content = ""
        async for chunk in llm.stream_chat(self.messages):
            full_content += chunk
            yield chunk
        self.messages.append(Message(role="assistant", content=full_content))

    async def _retrieve_context(self, query: str) -> str:
        """从知识库检索相关背景信息（RAG）"""
        try:
            from backend.retrieval.vector_store import VectorStore
            store = VectorStore()
            results = await store.search(query, top_k=3)
            if results:
                return "\n---\n".join(r["content"] for r in results)
        except Exception:
            pass
        return ""

    def get_message_history(self) -> list[Message]:
        """获取对话历史"""
        return self.messages

    def clear_history(self) -> None:
        """清空对话历史"""
        self.messages.clear()
