"""
智能体核心引擎。

协调多模型调用、知识检索、数据分析、NL2Query 代码生成与执行、记忆管理。
"""
from __future__ import annotations

import logging
from typing import AsyncIterator, Optional

from backend.models.base import BaseLLM, Message, ModelResponse
from backend.models.registry import ModelRegistry

logger = logging.getLogger("research_agent.core")


class ResearchAgent:
    """科研数据分析智能体"""

    def __init__(self, session_id: str, model_id: Optional[str] = None):
        self.session_id = session_id
        self.model_id = model_id or ModelRegistry._default_llm
        self.messages: list[Message] = []
        self._llm: Optional[BaseLLM] = None
        self._codegen_cache: dict = {}

    async def _get_llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = ModelRegistry.get_llm_with_fallback(self.model_id)
            if self._llm is None:
                raise ValueError(
                    "没有可用的 AI 模型。请在 .env 中配置 API Key 后重启服务。"
                )
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

    async def nl2query_code(self, query: str, data_type: str = "gnss",
                             data_description: str = "") -> dict:
        """将自然语言查询转为 Python 代码（需要 LLM 支持）"""
        from backend.analysis.codegen import generate_code
        return await generate_code(query, data_type, data_description,
                                    model_id=self.model_id)

    async def nl2query_execute(self, query: str, data_type: str = "gnss",
                                data_description: str = "",
                                use_cache: bool = True) -> dict:
        """将自然语言查询转为 Python 代码并执行"""
        from backend.core.sandbox import CodeSandbox
        from backend.analysis.cache import QueryCache

        # 1. Check cache
        if use_cache:
            cache = QueryCache()
            cached = cache.get(query, data_type)
            if cached is not None:
                logger.info("NL2Query cache hit: %s...", query[:50])
                return {
                    "success": True,
                    "from_cache": True,
                    "code": cached.get("code", ""),
                    "result": cached.get("result", {}),
                }

        # 2. Generate code
        gen_result = await self.nl2query_code(query, data_type, data_description)
        if not gen_result["success"]:
            return gen_result

        code = gen_result["code"]

        # 3. Execute in sandbox
        sandbox = CodeSandbox(timeout=30)
        try:
            exec_result = sandbox.execute_python(code)
            output = exec_result.to_dict()

            # 4. Cache result
            if use_cache and exec_result.success:
                cache = QueryCache()
                cache.set(query, data_type, code, output)

            return {
                "success": exec_result.success,
                "from_cache": False,
                "code": code,
                "result": output,
            }
        finally:
            sandbox.clean()

    async def _retrieve_context(self, query: str) -> str:
        """从知识库检索相关背景信息（RAG）"""
        try:
            from backend.retrieval.vector_store import get_vector_store
            store = get_vector_store()
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
