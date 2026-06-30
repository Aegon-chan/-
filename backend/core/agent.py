"""
????????

??????????????????NL2Query ?????????????
?? MemoryStore ?????????????????????????
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

from backend.models.base import BaseLLM, Message, ModelResponse
from backend.models.registry import ModelRegistry
from backend.core.memory import MemoryStore
from backend.core.strategy import StrategyLibrary

logger = logging.getLogger("research_agent.core")

# ?? ????????? ??????????????????????????????????????????

MEMORY_EXTRACT_SYSTEM_PROMPT = """??????????????????????????????????

## ????
1. **preference** ? ?????????????????????????
2. **knowledge** ? ??????????????????????????????????
3. **experience** ? ???????????????????????????????

## ????
? JSON ????????????? type, key, value, weight ???
?????????????? JSON?

?????
[
    {"type": "preference", "key": "??????", "value": "???? Word ???????", "weight": 0.8},
    {"type": "knowledge", "key": "????", "value": "???? GNSS ?????? 10mm ????", "weight": 1.0},
    {"type": "experience", "key": "????", "value": "?????????? + ?????? GNSS ??", "weight": 0.6}
]

?????????????? []?
"""


class ResearchAgent:
    """?????????"""

    def __init__(self, session_id: str, model_id: Optional[str] = None, user_id: str = "default"):
        self.session_id = session_id
        self.user_id = user_id
        self.model_id = model_id or ModelRegistry._default_llm
        self.messages: list[Message] = []
        self._llm: Optional[BaseLLM] = None
        self._codegen_cache: dict = {}
        self._memory_store: Optional[MemoryStore] = None
        self._memory_enabled: bool = True
        self._extraction_llm: Optional[BaseLLM] = None

    # ?? ???? ??????????????????????????????????????????????????

    @property
    def strategy(self) -> StrategyLibrary:
        if self._strategy is None:
            self._strategy = StrategyLibrary()
        return self._strategy

    @property
    def memory(self) -> MemoryStore:
        if self._memory_store is None:
            self._memory_store = MemoryStore()
        return self._memory_store

    async def _recall_memories(self, query: str, top_k: int = 5) -> str:
        """????????????????????????????"""
        if not self._memory_enabled:
            return ""
        try:
            keyword_results = self.memory.search(self.user_id, query, top_k=top_k)
            pref_results = self.memory.get(self.user_id, memory_type="preference", top_k=3)
            knowledge_results = self.memory.get(self.user_id, memory_type="knowledge", top_k=3)
            experience_results = self.memory.get(self.user_id, memory_type="experience", top_k=3)
            all_memories = keyword_results
            seen_keys = set()
            for m in pref_results + knowledge_results + experience_results:
                if m.get("key") not in seen_keys:
                    seen_keys.add(m.get("key"))
                    if m not in all_memories:
                        all_memories.append(m)
            if not all_memories:
                return ""
            lines = []
            for m in all_memories:
                mtype = m.get("memory_type", "unknown")
                key = m.get("key", "")
                value = m.get("value", "")
                weight = m.get("weight", 1.0)
                if weight > 0.3:
                    lines.append(f"[{mtype}] {key}: {value} (weight={weight:.2f})")
            if not lines:
                return ""
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Memory recall failed: %s", e)
            return ""

    async def _extract_and_store_memories(self, user_input: str, assistant_response: str) -> None:
        """?????????????????"""
        if not self._memory_enabled or not self._extraction_llm:
            return
        try:
            extract_messages = [
                Message(role="system", content=MEMORY_EXTRACT_SYSTEM_PROMPT),
                Message(role="user", content=f"??: {user_input}\n\n??: {assistant_response}"),
            ]
            response = await self._extraction_llm.chat(extract_messages, temperature=0.1, max_tokens=1000)
            memories = json.loads(response.content)
            if not isinstance(memories, list):
                return
            for mem in memories:
                if not isinstance(mem, dict):
                    continue
                mtype = mem.get("type", "knowledge")
                if mtype not in ("preference", "knowledge", "experience"):
                    continue
                key = str(mem.get("key", ""))[:256]
                value = str(mem.get("value", ""))
                weight = float(mem.get("weight", 0.5))
                if key and value:
                    self.memory.add(
                        user_id=self.user_id,
                        memory_type=mtype,
                        key=key,
                        value=value,
                        weight=weight,
                        source=f"session:{self.session_id}",
                        metadata={"session_id": self.session_id},
                    )
                    logger.info("Memory stored: [%s] %s = %s", mtype, key, value[:60])
        except (json.JSONDecodeError, Exception) as e:
            logger.debug("Memory extraction skipped: %s", e)

    # ?? LLM ?? ??????????????????????????????????????????????????

    async def _get_llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = ModelRegistry.get_llm_with_fallback(self.model_id)
            if self._llm is None:
                raise ValueError("????? AI ????? .env ??? API Key ??????")
        return self._llm

    async def _get_extraction_llm(self) -> Optional[BaseLLM]:
        if self._extraction_llm is None:
            for mid in ["deepseek-chat", "gpt-4o", "moonshot-v1"]:
                llm = ModelRegistry.get_llm(mid)
                if llm is not None:
                    self._extraction_llm = llm
                    break
        return self._extraction_llm

    # ?? ?? ??????????????????????????????????????????????????????

    async def chat(self, user_input: str) -> ModelResponse:
        """????????????????"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        memory_context = await self._recall_memories(user_input)
        rag_context = await self._retrieve_context(user_input)
        context_parts = []
        if memory_context:
            context_parts.append(f"[????]\n{memory_context}")
        if rag_context:
            context_parts.append(f"[???]\n{rag_context}")
        if context_parts:
            combined = "\n\n".join(context_parts)
            self.messages.append(Message(role="system", content=combined))
        response = await llm.chat(self.messages)
        self.messages.append(response)
        extraction_llm = await self._get_extraction_llm()
        if extraction_llm:
            await self._extract_and_store_memories(user_input, response.content)
        return response

    async def stream_chat(self, user_input: str) -> AsyncIterator[str]:
        """??????????????"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        memory_context = await self._recall_memories(user_input)
        rag_context = await self._retrieve_context(user_input)
        context_parts = []
        if memory_context:
            context_parts.append(f"[????]\n{memory_context}")
        if rag_context:
            context_parts.append(f"[???]\n{rag_context}")
        if context_parts:
            combined = "\n\n".join(context_parts)
            self.messages.append(Message(role="system", content=combined))
        full_content = ""
        async for chunk in llm.stream_chat(self.messages):
            full_content += chunk
            yield chunk
        self.messages.append(Message(role="assistant", content=full_content))
        extraction_llm = await self._get_extraction_llm()
        if extraction_llm:
            await self._extract_and_store_memories(user_input, full_content)

    # ?? NL2Query ??????????????????????????????????????????????????

    async def nl2query_code(self, query: str, data_type: str = "gnss", data_description: str = "") -> dict:
        from backend.analysis.codegen import generate_code
        return await generate_code(query, data_type, data_description, model_id=self.model_id)

    async def nl2query_execute(self, query: str, data_type: str = "gnss", data_description: str = "", use_cache: bool = True) -> dict:
        from backend.core.sandbox import CodeSandbox
        from backend.analysis.cache import QueryCache
        if use_cache:
            cache = QueryCache()
            cached = cache.get(query, data_type)
            if cached is not None:
                logger.info("NL2Query cache hit: %s...", query[:50])
                return {"success": True, "from_cache": True, "code": cached.get("code", ""), "result": cached.get("result", {})}
        gen_result = await self.nl2query_code(query, data_type, data_description)
        if not gen_result["success"]:
            return gen_result
        code = gen_result["code"]
        sandbox = CodeSandbox(timeout=30)
        try:
            exec_result = sandbox.execute_python(code)
            output = exec_result.to_dict()
            if use_cache and exec_result.success:
                cache = QueryCache()
                cache.set(query, data_type, code, output)
            return {"success": exec_result.success, "from_cache": False, "code": code, "result": output}
        finally:
            sandbox.clean()

    # ?? RAG ?? ??????????????????????????????????????????????????

    async def _retrieve_context(self, query: str) -> str:
        try:
            from backend.retrieval.vector_store import get_vector_store
            store = get_vector_store()
            results = await store.search(query, top_k=3)
            if results:
                return "\n---\n".join(r["content"] for r in results)
        except Exception:
            pass
        return ""

    # ?? ?????? ??????????????????????????????????????????????

    def get_message_history(self) -> list[Message]:
        return self.messages

    def clear_history(self) -> None:
        self.messages.clear()

    def list_memories(self, memory_type: Optional[str] = None, top_k: int = 20) -> list[dict]:
        return self.memory.get(user_id=self.user_id, memory_type=memory_type, top_k=top_k)

    def search_memories(self, query: str, top_k: int = 5) -> list[dict]:
        return self.memory.search(user_id=self.user_id, query=query, top_k=top_k)

    def delete_memory(self, memory_id: int) -> None:
        self.memory.delete(memory_id)

    def toggle_memory(self, enabled: Optional[bool] = None) -> bool:
        if enabled is not None:
            self._memory_enabled = enabled
        else:
            self._memory_enabled = not self._memory_enabled
        return self._memory_enabled

    def toggle_react(self, enabled = None) -> bool:
        if enabled is not None:
            self._react_enabled = enabled
        else:
            self._react_enabled = not self._react_enabled
        return self._react_enabled

    def get_strategies(self, task_type: str = "analysis", top_k: int = 10) -> list[dict]:
        return self.strategy.get_top(task_type, top_k=top_k)
