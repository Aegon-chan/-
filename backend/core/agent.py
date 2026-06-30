"""
ResearchAgent —— 核心智能体

整合 NL2Query、记忆系统、策略库、反馈闭环、Prompt 优化、LoRA 微调。
"""

from __future__ import annotations

import json
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import AsyncIterator, Optional

from backend.models.base import BaseLLM, Message, ModelResponse
from backend.models.registry import ModelRegistry
from backend.core.memory import MemoryStore
from backend.core.strategy import StrategyLibrary
from backend.self_growth.feedback import FeedbackCollector
from backend.self_growth.prompt_optimizer import PromptOptimizer
from backend.self_growth.memory_optimizer import MemoryOptimizer
from backend.self_growth.finetune import FineTuner

logger = logging.getLogger("research_agent.core")

# ---------------------------------------------------------------------------
# 记忆提取系统提示
# ---------------------------------------------------------------------------

MEMORY_EXTRACT_SYSTEM_PROMPT = """你是一个记忆提取助手。从用户与助手的对话中提取有价值的记忆。

## 记忆类型
1. **preference** —— 用户的格式偏好、模型偏好、术语偏好等
2. **knowledge** —— 用户提到的领域知识、规范条文、监测数据特征
3. **experience** —— 成功/失败的分析策略、解决思路

## 输出格式
以 JSON 数组格式输出，每个元素包含 type, key, value, weight 字段。
只输出合法 JSON，不要包含其他文字。

示例:
[
    {"type": "preference", "key": "报告格式偏好", "value": "用户倾向于 Word 格式的报告", "weight": 0.8},
    {"type": "knowledge", "key": "监测精度要求", "value": "用户提到 GNSS 监测精度需达到 10mm", "weight": 1.0},
    {"type": "experience", "key": "形变分析方法", "value": "用户成功使用时间序列分解 + 突变检测分析 GNSS 数据", "weight": 0.6}
]

若没有可提取的记忆，返回 []。
"""

# ---------------------------------------------------------------------------
# 自成长配置默认值
# ---------------------------------------------------------------------------

HIGH_QUALITY_RATING_THRESHOLD = 3  # 视为优质反馈的最低评分
FINETUNE_AUTO_TRIGGER_COUNT = 20   # 自动触发微调所需的高质量反馈条数
OPTIMIZATION_INTERVAL_MINUTES = 30 # 后台优化任务运行间隔（分钟）
MEMORY_DECAY_INTERVAL_HOURS = 6    # 记忆权重衰减间隔（小时）
MEMORY_MERGE_INTERVAL_HOURS = 12   # 记忆合并间隔（小时）
PROMPT_EVAL_INTERVAL_HOURS = 24    # Prompt 自动评估间隔（小时）


class ResearchAgent:
    """自成长型科研数据分析智能体。"""

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

        # ---- 自成长模块 ----
        self._feedback_collector: Optional[FeedbackCollector] = None
        self._prompt_optimizer: Optional[PromptOptimizer] = None
        self._memory_optimizer: Optional[MemoryOptimizer] = None
        self._fine_tuner: Optional[FineTuner] = None
        self._optimization_enabled: bool = True
        self._feedbacks_since_optimization: int = 0
        self._last_decay_time: float = time.time()
        self._last_merge_time: float = time.time()
        self._last_prompt_eval_time: float = time.time()
        self._optimization_thread: Optional[threading.Thread] = None

        # 启动后台优化线程
        if self._optimization_enabled:
            self._start_optimization_thread()

    # ═══════════════════════════ 核心属性 ═══════════════════════════

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

    @property
    def feedback_collector(self) -> FeedbackCollector:
        """用户隔离的反馈收集器。"""
        if self._feedback_collector is None:
            db_path = f"./data/feedback_{self.user_id}.db"
            self._feedback_collector = FeedbackCollector(db_path=db_path)
        return self._feedback_collector

    @property
    def prompt_optimizer(self) -> PromptOptimizer:
        """用户隔离的 Prompt 优化器。"""
        if self._prompt_optimizer is None:
            db_path = f"./data/prompts_{self.user_id}.db"
            self._prompt_optimizer = PromptOptimizer(db_path=db_path)
        return self._prompt_optimizer

    @property
    def memory_optimizer(self) -> MemoryOptimizer:
        if self._memory_optimizer is None:
            self._memory_optimizer = MemoryOptimizer()
        return self._memory_optimizer

    @property
    def fine_tuner(self) -> FineTuner:
        """用户隔离的微调管理器。"""
        if self._fine_tuner is None:
            checkpoint_dir = f"./data/lora_checkpoints/{self.user_id}"
            self._fine_tuner = FineTuner(checkpoint_dir=checkpoint_dir)
        return self._fine_tuner

    # ═══════════════════════════ 后台优化线程 ═══════════════════════════

    def _start_optimization_thread(self):
        """启动后台优化守护线程。"""
        if self._optimization_thread and self._optimization_thread.is_alive():
            return

        def _run():
            while self._optimization_enabled:
                try:
                    self._run_optimization_cycle()
                except Exception as e:
                    logger.warning("Optimization cycle error: %s", e)
                time.sleep(OPTIMIZATION_INTERVAL_MINUTES * 60)

        self._optimization_thread = threading.Thread(target=_run, daemon=True)
        self._optimization_thread.start()
        logger.info("Background optimization thread started (interval=%s min, user=%s)",
                     OPTIMIZATION_INTERVAL_MINUTES, self.user_id)

    def _run_optimization_cycle(self):
        """执行一轮后台优化任务。"""
        now = time.time()
        elapsed_hours = (now - self._last_decay_time) / 3600

        # 记忆权重衰减 (每 6 小时)
        if elapsed_hours >= MEMORY_DECAY_INTERVAL_HOURS:
            try:
                self.memory.decay_weights(factor=0.95)
                self._last_decay_time = now
                logger.info("Memory decay cycle completed (user=%s)", self.user_id)
            except Exception as e:
                logger.warning("Memory decay failed: %s", e)

        # 记忆合并 (每 12 小时)
        merge_hours = (now - self._last_merge_time) / 3600
        if merge_hours >= MEMORY_MERGE_INTERVAL_HOURS:
            try:
                mems = self.memory.get(user_id=self.user_id, top_k=200)
                merged = self.memory_optimizer.merge(mems, similarity_threshold=0.7)
                if len(merged) < len(mems):
                    logger.info("Memory merge: %d -> %d (user=%s)",
                                len(mems), len(merged), self.user_id)
                self._last_merge_time = now
            except Exception as e:
                logger.warning("Memory merge failed: %s", e)

        # Prompt 自动评估 (每 24 小时)
        prompt_hours = (now - self._last_prompt_eval_time) / 3600
        if prompt_hours >= PROMPT_EVAL_INTERVAL_HOURS and self._feedbacks_since_optimization >= 5:
            try:
                feedbacks = self.feedback_collector.get_feedback_by_user(self.user_id, limit=50)
                async def _do_optimize():
                    import asyncio
                    for task_type in ["analysis", "retrieval", "report"]:
                        await self.prompt_optimizer.optimize(task_type, feedbacks)
                import asyncio
                asyncio.run(_do_optimize())
                self._feedbacks_since_optimization = 0
                self._last_prompt_eval_time = now
                logger.info("Prompt auto-evaluation cycle completed (user=%s)", self.user_id)
            except Exception as e:
                logger.warning("Prompt evaluation failed: %s", e)

        # LoRA 微调自动触发
        try:
            high_quality = self.feedback_collector.get_stats().get("high_quality_count", 0)
            trained = len(self.fine_tuner.list_models())
            if high_quality >= FINETUNE_AUTO_TRIGGER_COUNT and trained == 0:
                feedbacks = self.feedback_collector.get_feedback_by_user(self.user_id, limit=200)
                training_data = self.feedback_collector.to_training_data(min_rating=HIGH_QUALITY_RATING_THRESHOLD)
                if len(training_data) >= FINETUNE_AUTO_TRIGGER_COUNT:
                    dataset_path = self.fine_tuner.prepare_dataset(training_data)
                    logger.info("Auto-trigger fine-tuning: %d samples (user=%s)",
                                len(training_data), self.user_id)
        except Exception as e:
            logger.debug("Fine-tune check skipped: %s", e)

    # ═══════════════════════════ 记忆检索 ═══════════════════════════

    async def _recall_memories(self, query: str, top_k: int = 5) -> str:
        """从向量/关键词检索记忆并格式化为上下文文本。"""
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
        """从对话中提取记忆并持久化。"""
        if not self._memory_enabled or not self._extraction_llm:
            return
        try:
            extract_messages = [
                Message(role="system", content=MEMORY_EXTRACT_SYSTEM_PROMPT),
                Message(role="user", content=f"用户: {user_input}\n\n助手: {assistant_response}"),
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

    # ═══════════════════════════ LLM 获取 ═══════════════════════════

    async def _get_llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = ModelRegistry.get_llm_with_fallback(self.model_id)
            if self._llm is None:
                raise ValueError("未检测到可用的 AI 模型，请检查 .env 中 API Key 配置是否正确")
        return self._llm

    async def _get_extraction_llm(self) -> Optional[BaseLLM]:
        if self._extraction_llm is None:
            for mid in ["deepseek-chat", "gpt-4o", "moonshot-v1"]:
                llm = ModelRegistry.get_llm(mid)
                if llm is not None:
                    self._extraction_llm = llm
                    break
        return self._extraction_llm

    # ═══════════════════════════ 自我成长接口 ═══════════════════════════

    def submit_feedback(self, message_id: str, rating: int, comment: str = "",
                        tags: list = None, session_id: str = "") -> dict:
        """提交反馈并触发异步记忆提取 + Prompt 优化。

        Args:
            message_id: 消息 ID
            rating: 评分 (1-5, 或 -1 表示负面)
            comment: 文字评价
            tags: 标签列表
            session_id: 会话 ID

        Returns:
            反馈收集结果
        """
        tags = tags or []

        # 1. 收集反馈
        result = self.feedback_collector.collect(
            message_id=message_id,
            rating=rating,
            comment=comment,
            tags=tags,
            user_id=self.user_id,
            session_id=session_id or self.session_id,
        )
        feedback_id = result.get("id", 0)

        # 2. 使用 MemoryOptimizer 计算权重调整
        weight_delta = self.memory_optimizer.update_weight(rating)

        # 3. 将反馈内容写入记忆（异步风格，但同步执行）
        try:
            feedback_data = {
                "comment": comment,
                "tags": tags,
                "rating": rating,
                "content": f"评分 {rating}: {comment}",
            }
            memory_ids = self.memory.store_feedback_memory(self.user_id, feedback_data)
            if memory_ids and weight_delta != 0:
                for mid in memory_ids:
                    self.memory.update_weight(mid, weight_delta)
        except Exception as e:
            logger.debug("Feedback memory store skipped: %s", e)

        # 4. 计数优质反馈
        if rating >= HIGH_QUALITY_RATING_THRESHOLD:
            self._feedbacks_since_optimization += 1

        return {
            "feedback_id": feedback_id,
            "rating": rating,
            "weight_delta": weight_delta,
            "memories_stored": len(locals().get("memory_ids", [])),
            "message": "反馈已记录，系统将根据反馈持续优化" if rating >= HIGH_QUALITY_RATING_THRESHOLD else "反馈已记录",
        }

    def get_optimized_prompt(self, task_type: str) -> str:
        """获取当前最优的 Prompt 模板。

        Args:
            task_type: 任务类型 (analysis / retrieval / report)

        Returns:
            优化后的 prompt 内容；若无则返回空字符串
        """
        try:
            template = self.prompt_optimizer.get_template(task_type)
            if template:
                return template["content"]
        except Exception as e:
            logger.debug("Prompt retrieval failed: %s", e)
        return ""

    # ═══════════════════════════ 对话接口 ═══════════════════════════

    async def chat(self, user_input: str) -> ModelResponse:
        """处理用户对话，整合记忆上下文。"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        memory_context = await self._recall_memories(user_input)
        rag_context = await self._retrieve_context(user_input)
        context_parts = []
        if memory_context:
            context_parts.append(f"[记忆]\n{memory_context}")
        if rag_context:
            context_parts.append(f"[知识]\n{rag_context}")
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
        """流式对话，逐 token 产出。"""
        llm = await self._get_llm()
        self.messages.append(Message(role="user", content=user_input))
        memory_context = await self._recall_memories(user_input)
        rag_context = await self._retrieve_context(user_input)
        context_parts = []
        if memory_context:
            context_parts.append(f"[记忆]\n{memory_context}")
        if rag_context:
            context_parts.append(f"[知识]\n{rag_context}")
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

    # ═══════════════════════════ NL2Query 接口 ═══════════════════════════

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

    # ═══════════════════════════ RAG 检索 ═══════════════════════════

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

    # ═══════════════════════════ 工具方法 ═══════════════════════════

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

    # ═══════════════════════════ 优化状态 ═══════════════════════════

    def get_optimization_stats(self) -> dict:
        """获取自成长模块的统计信息。"""
        try:
            memory_stats = self.memory.get_stats(self.user_id)
        except Exception:
            memory_stats = {"total": 0, "by_type": {}}
        try:
            feedback_stats = self.feedback_collector.get_stats()
        except Exception:
            feedback_stats = {}
        try:
            finetune_models = self.fine_tuner.list_models()
        except Exception:
            finetune_models = []
        try:
            prompt_versions = {}
            for task_type in ["analysis", "retrieval", "report"]:
                tpl = self.prompt_optimizer.get_template(task_type)
                if tpl:
                    prompt_versions[task_type] = {"version": tpl.get("version", 0), "score": tpl.get("score", 0)}
        except Exception:
            prompt_versions = {}

        return {
            "user_id": self.user_id,
            "memory": memory_stats,
            "feedback": feedback_stats,
            "finetune": {
                "models": len(finetune_models),
                "active_model": next((m for m in finetune_models if m.get("is_active")), None),
            },
            "prompt": prompt_versions,
            "optimization_enabled": self._optimization_enabled,
            "feedbacks_since_optimization": self._feedbacks_since_optimization,
        }

    def toggle_optimization(self, enabled: Optional[bool] = None) -> bool:
        """启用/禁用后台优化任务。"""
        if enabled is not None:
            self._optimization_enabled = enabled
        else:
            self._optimization_enabled = not self._optimization_enabled

        if self._optimization_enabled:
            self._start_optimization_thread()
        return self._optimization_enabled


