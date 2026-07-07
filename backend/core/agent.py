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
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from backend.models.base import BaseLLM, ContentPart, Message, ModelResponse
from backend.uploads import extract_text_from_file, image_to_data_uri
from pathlib import Path
from backend.models.registry import ModelRegistry
from backend.core.memory import MemoryStore
from backend.core.strategy import StrategyLibrary
from backend.self_growth.feedback import FeedbackCollector
from backend.self_growth.prompt_optimizer import PromptOptimizer
from backend.self_growth.memory_optimizer import MemoryOptimizer
from backend.self_growth.finetune import FineTuner
from backend.self_growth.implicit_feedback import ImplicitFeedbackCollector
from backend.self_growth.progressive import ProgressiveLearner

logger = logging.getLogger("research_agent.core")

# ---------------------------------------------------------------------------
# ReAct 系统提示
# ---------------------------------------------------------------------------

REACT_SYSTEM_PROMPT = """你是 Research Agent，一个具备推理和行动能力的科研数据分析智能体。

请按照以下步骤思考并解决问题：

## 可用工具

1. `analyze_data(query: str, data_type: str)` - 将自然语言分析需求转化为 Python 代码并执行。
   data_type 可选: gnss, insar, rainfall, groundwater, pore_pressure

2. `search_knowledge(query: str)` - 在知识库中检索相关文档。

3. `search_memory(query: str)` - 在长期记忆中检索用户的偏好、知识和经验。

4. `generate_report(report_type: str, data: dict)` - 生成监测报告（html/docx/pdf）。
   report_type 可选: daily, weekly, monthly, special

5. `final_answer(answer: str)` - 输出最终答案，结束推理。

## 推理格式

每次输出必须包含以下 JSON 结构（只输出 JSON，不要有其他文字）：

```json
{
  "thought": "你当前的思考...",
  "action": "工具名称或 final_answer",
  "action_input": {"参数名": "参数值"}
}
```

## 规则
- 每次只调用一个工具
- 根据观察结果决定下一步行动
- 分析问题时一步步推理
- 当问题已解决或无法继续时，使用 final_answer 输出最终回答
"""

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



# ──────────────────── 附件处理辅助函数 ────────────────────


def _process_attachments(attachments: list[dict] | None) -> list[ContentPart]:
    """将前端上传的附件转为 ContentPart 列表，供多模态消息使用。

    图片 -> base64 data URI -> ContentPart(type="image_base64")
    文档（PDF/DOCX/TXT/MD）-> 文本提取 -> ContentPart(type="text")
    """
    if not attachments:
        return []
    parts: list[ContentPart] = []
    upload_root = Path("data") / "uploads"
    for att in attachments:
        url = att.get("url", "")
        mime = att.get("mime_type", "")
        fname = Path(url).name
        file_path = upload_root / fname
        if not file_path.exists():
            continue
        try:
            if mime.startswith("image/"):
                data_uri = image_to_data_uri(str(file_path))
                if data_uri:
                    parts.append(ContentPart(type="image_base64", image_base64=data_uri, mime_type=mime))
            else:
                text = extract_text_from_file(str(file_path), mime)
                if text:
                    parts.append(ContentPart(type="text", text=text))
        except Exception:
            continue
    return parts


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
        self._react_enabled: bool = False
        self._react_max_iterations: int = 10

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
        self._strategy: Optional[StrategyLibrary] = None

        # 启动后台优化线程
        self._implicit_feedback: Optional[ImplicitFeedbackCollector] = None
        self._progressive = ProgressiveLearner()

        self._learning_mode: bool = False

        if self._optimization_enabled:
            self._start_optimization_thread()

    # ═══════════════════════════ 核心属性 ═══════════════════════════

    @property
    def implicit_feedback(self) -> ImplicitFeedbackCollector:
        """Lazy-initialized implicit feedback collector."""
        if self._implicit_feedback is None:
            from backend.config import settings
            self._implicit_feedback = ImplicitFeedbackCollector(
                db_path=f"./data/feedback_{self.user_id}.db",
                enable=getattr(settings, "feature_implicit_feedback", True),
            )
        return self._implicit_feedback

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
                    import asyncio

                    dataset_path = asyncio.run(self.fine_tuner.prepare_dataset(training_data))
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
        memory_ids: list[int] = []

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
            "memories_stored": len(memory_ids),
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

    # ═══════════════════════════ 意图检测与工具编排 ═══════════════════════════

    def _detect_intent(self, user_input: str) -> dict:
        """检测用户查询是否需要数据分析或报告生成。

        Returns:
            dict: {needs_analysis, needs_report, data_type, analysis_query}
        """
        text = user_input.lower()

        analysis_patterns = {
            "gnss": ["gnss", "gps", "位移", "形变", "沉降", "变形", "displacement", "deformation", "settlement"],
            "insar": ["insar", "sar", "雷达", "干涉", "radar", "interferometry"],
            "rainfall": ["降雨", "降水", "雨量", "暴雨", "降雨量", "rainfall", "precipitation", "rain"],
            "groundwater": ["地下水", "水位", "潜水", "地下水位", "groundwater", "water level", "ground water"],
            "pore_pressure": ["孔压", "孔隙水", "孔隙压力", "超静孔压", "pore pressure", "pore", "porewater"],
        }

        general_analysis = [
            "分析", "计算", "绘图", "画图", "统计", "趋势", "突变",
            "异常检测", "滤波", "分解", "速率", "预测",
            "analyze", "calculate", "plot", "chart", "trend", "detect",
            "anomaly", "filter", "decompose", "velocity", "predict",
        ]

        report_indicators = [
            "报告", "报表", "汇报", "日报", "周报", "月报", "年报",
            "生成报告", "出报告", "导出报告",
            "report", "daily report", "monthly report", "weekly report",
        ]

        data_query_indicators = [
            "查一下", "查查", "查看", "显示", "展示",
            "最近", "最新", "今天", "昨天", "这个月", "上个月",
            "统计", "多少", "范围", "最大", "最小", "平均",
            "数据", "监测数据", "查询", "读数是", "是多少",
        ]


        data_type = "gnss"
        needs_analysis = False

        for dtype, keywords in analysis_patterns.items():
            if any(kw in text for kw in keywords):
                data_type = dtype
                needs_analysis = True
                break

        if not needs_analysis:
            for indicator in general_analysis:
                if indicator in text:
                    needs_analysis = True
                    break

        needs_report = any(indicator in text for indicator in report_indicators)

        needs_data_query = any(indicator in text for indicator in data_query_indicators)

        # If data query detected but no analysis type matched, still mark as data query
        if needs_data_query and not needs_analysis:
            needs_analysis = True  # Trigger analysis path for data display

        return {
            "needs_analysis": needs_analysis,
            "needs_report": needs_report,
            "needs_data_query": needs_data_query,
            "analysis_query": user_input,
        }

    def _format_analysis_summary(self, result: dict) -> str:
        """将 NL2Query 分析结果格式化为结构化文本，供 LLM 理解。"""
        if not result.get("success"):
            err_raw = result.get("error", "") or result.get("result", {}).get("stderr", "") or result.get("result", {}).get("stdout", "")[:200]
            if "ModuleNotFoundError" in err_raw:
                err_display = "沙箱中缺少所需 Python 包，图表生成失败"
            else:
                err_display = err_raw[:200] if err_raw else "未知错误"
            return f"分析执行失败: {err_display}"

        res = result.get("result", {})
        parts = []

        stdout = res.get("stdout", "").strip()
        if stdout:
            parts.append(f"分析输出:\n```\n{stdout[:2000]}\n```")

        data = res.get("data", {})
        if data:
            import json
            parts.append(f"关键数据:\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}\n```")

        code = result.get("code", "")
        if code:
            parts.append(f"生成的 Python 代码:\n```python\n{code[:1000]}\n```")

        figures = res.get("figures", [])
        if figures:
            parts.append(f"生成了 {len(figures)} 张图表")

        exec_time = res.get("execution_time_ms", 0)
        if exec_time:
            parts.append(f"执行耗时: {int(exec_time)}ms")

        return "\n\n".join(parts)

    def _format_analysis_stream(self, result: dict) -> str:
        """将分析结果格式化为面向用户的流式输出文本。"""
        if not result.get("success"):
            err_raw = result.get("error", "") or result.get("result", {}).get("stderr", "") or result.get("result", {}).get("stdout", "")[:200]
            if "ModuleNotFoundError" in err_raw:
                err_display = "沙箱中缺少所需 Python 包，图表生成失败"
            else:
                err_display = err_raw[:200] if err_raw else "未知错误"
            return f"❌ 分析执行失败: {err_display}"

        res = result.get("result", {})
        lines = ["✅ **数据分析完成**\n"]

        stdout = res.get("stdout", "").strip()
        if stdout:
            lines.append(f"**分析输出**:\n```\n{stdout[:1000]}\n```")

        data = res.get("data", {})
        if data:
            import json
            summary = json.dumps(data, ensure_ascii=False)[:500]
            lines.append(f"**关键数据**: {summary}")

        figures = res.get("figures", [])
        if figures:
            lines.append(f"📊 生成了 {len(figures)} 张图表")

        return "\n".join(lines)

    async def _integrated_analysis(self, query: str, data_type: str = "gnss",
                                    generate_report: bool = False) -> dict:
        """运行 NL2Query 分析，可选生成报告，返回格式化结果。"""
        result = {
            "analysis_result": None,
            "analysis_text": "",
            "analysis_stream": "",
            "figures": [],
            "report_text": "",
            "report_stream": "",
        }

        analysis_result = await self.nl2query_execute(query=query, data_type=data_type, use_cache=True)
        result["analysis_result"] = analysis_result
        result["analysis_text"] = self._format_analysis_summary(analysis_result)
        result["analysis_stream"] = self._format_analysis_stream(analysis_result)
        result["figures"] = analysis_result.get("result", {}).get("figures", [])

        # 保存图表到 uploads 目录，供前端内联显示
        figures = result["figures"]
        if figures:
            import base64, uuid
            from pathlib import Path
            uploads_dir = Path("data") / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            figure_md_lines = []
            for i, fig in enumerate(figures):
                b64 = fig.get("b64", "")
                if b64:
                    try:
                        img_bytes = base64.b64decode(b64)
                        fig_name = f"analysis_{uuid.uuid4().hex[:8]}_{i}.png"
                        fig_path = uploads_dir / fig_name
                        fig_path.write_bytes(img_bytes)
                        figure_md_lines.append(f"![图表{i+1}](/uploads/{fig_name})")
                    except Exception:
                        pass
            if figure_md_lines:
                figures_md = "\n".join(figure_md_lines)
                result["analysis_stream"] += f"\n\n{figures_md}"

        # 可选生成报告
        if generate_report and analysis_result.get("success"):
            report_data = {
                "title": f"{data_type.upper()} 分析报告",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "query": query,
            }
            result_data = analysis_result.get("result", {})
            if result_data:
                report_data["analysis"] = result_data
                report_data["stdout"] = result_data.get("stdout", "")
                report_data["data"] = result_data.get("data", {})

            try:
                report_path = await self._react_tool_generate_report(report_type="daily", data=report_data)
                report_path_str = str(report_path)
                result["report_text"] = f"报告已生成: {report_path_str}"
                result["report_stream"] = f"✅ **报告已生成**: [{report_path_str}]({report_path_str})\n\n"
            except Exception as e:
                logger.warning("Report generation failed: %s", e)
                result["report_text"] = f"报告生成失败: {e}"

        return result

    # ═══════════════════════════ 对话接口（增强版） ═══════════════════════════


    # ============================================================
    # 监测数据库查询
    # ============================================================

    async def _query_monitoring_data(self, data_type: str = "groundwater", query: str = "") -> str:
        """查询监测数据库，返回结构化文本供 LLM 使用。"""
        try:
            from backend.analysis.monitoring_service import (
                get_latest as svc_get_latest,
                get_summary as svc_get_summary,
                query_measurements,
            )
            from backend.db.monitoring_session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                # Try latest data first
                latest = await svc_get_latest(db, data_type)
                if latest.get("success") and latest.get("records"):
                    records = latest["records"]
                    lines = [
                        f"数据类型: {data_type}",
                        f"站点数: {len(records)}",
                    ]
                    for r in records[:10]:
                        station = r.get("station_code", r.get("station_id", ""))
                        time_val = r.get("measurement_time", "")
                        vals = "; ".join(f"{k}={v}" for k, v in r.get("values", {}).items())
                        lines.append(f"  - {station} ({time_val}): {vals}")
                    return "\n".join(lines)

                # If no latest data, try summary
                summary = await svc_get_summary(db, data_type)
                if summary.get("success"):
                    return (
                        f"数据类型: {data_type}\n"
                        f"总记录数: {summary.get("total_records", 0)}\n"
                        f"站点数: {summary.get("station_count", 0)}\n"
                        f"时间范围: {summary.get("time_range", {}).get("start", "")} ~ {summary.get("time_range", {}).get("end", "")}"
                    )

            return f"监测数据库中没有 {data_type} 类型的数据"
        except ImportError:
            return "(监测数据库模块未加载)"
        except Exception as e:
            return f"(查询监测数据出错: {e})"

    async def chat(self, user_input: str, attachments: list[dict] | None = None) -> ModelResponse:
        """处理用户对话，整合记忆、知识库、数据分析、报告生成。"""
        llm = await self._get_llm()

        # 1. 记忆召回
        memory_context = await self._recall_memories(user_input)

        # 2. RAG 知识库检索
        rag_context = await self._retrieve_context(user_input)

        # 3. 意图检测
        intent = self._detect_intent(user_input)

        # 4. 构建上下文
        context_parts = []
        if memory_context:
            context_parts.append(f"## 用户长期记忆\\n{memory_context}")
        if rag_context:
            context_parts.append(f"## 知识库参考内容\\n{rag_context}")

        # 5. 执行集成分析（含报告生成）
        if intent["needs_analysis"] or intent["needs_report"]:
            try:
                integrated = await self._integrated_analysis(
                    query=intent["analysis_query"],
                    data_type=intent["data_type"],
                    generate_report=intent["needs_report"],
                )
                if integrated["analysis_text"]:
                    context_parts.append(f"## 数据分析结果\n{integrated["analysis_text"]}")
                if integrated["report_text"]:
                    context_parts.append(f"## 报告信息\n{integrated["report_text"]}")
            except Exception as e:
                logger.exception("Integrated analysis failed")
                context_parts.append(f"## 分析过程异常\n{e}")

        # 6. 插入上下文系统消息（在用户消息之前），然后添加用户消息
        system_msg_content = None
        if context_parts:
            instructions = (
                "请严格依据以下知识库内容和用户记忆来回答问题。\n"
                "如果提供的参考信息与问题相关，请优先使用参考信息作答；"
                "如果参考信息不相关或不足，则忽略它们并基于自身知识正常回答。\n"
            )
            system_msg_content = instructions + "\n\n" + "\n\n".join(context_parts)

        multimodal_parts = _process_attachments(attachments)
        self.messages.append(Message(role="user", content=user_input, multimodal_parts=multimodal_parts))
        self.implicit_feedback.record_query(self.session_id, user_input, self.user_id)

        if system_msg_content:
            self.messages.insert(0, Message(role="system", content=system_msg_content))


        response = await llm.chat(self.messages)
        self.messages.append(response)

        # 7. 记忆提取
        extraction_llm = await self._get_extraction_llm()
        if extraction_llm:
            await self._extract_and_store_memories(user_input, response.content)

        return response

    async def stream_chat(self, user_input: str, attachments: list[dict] | None = None) -> AsyncIterator[str]:
        """流式对话，整合记忆、知识库、数据分析、报告生成，逐 token 产出。"""
        llm = await self._get_llm()

        # 1. 记忆召回
        memory_context = await self._recall_memories(user_input)

        # 2. RAG 知识库检索
        rag_context = await self._retrieve_context(user_input)

        # 3. 意图检测
        intent = self._detect_intent(user_input)

        context_parts = []
        if memory_context:
            context_parts.append(f"## 用户长期记忆\\n{memory_context}")
        if rag_context:
            context_parts.append(f"## 知识库参考内容\\n{rag_context}")

        # 4. 执行集成分析

        # 4a. 监测数据库查询
        if intent.get("needs_data_query"):
            monitoring_context = await self._query_monitoring_data(
                data_type=intent.get("data_type", "groundwater"),
                query=intent.get("analysis_query", ""),
            )
            if monitoring_context:
                context_parts.append(f"## 监测数据库查询结果\n{monitoring_context}")

        if intent["needs_analysis"]:
            yield "⏳ **正在分析数据...**\n\n"
            try:
                integrated = await self._integrated_analysis(
                    query=intent["analysis_query"],
                    data_type=intent["data_type"],
                    generate_report=intent["needs_report"],
                )
                if integrated["analysis_text"]:
                    context_parts.append(f"## 数据分析结果\n{integrated["analysis_text"]}")
                if integrated["analysis_stream"]:
                    yield integrated["analysis_stream"]
                    yield "\n\n"
                if integrated["report_text"]:
                    context_parts.append(f"## 报告信息\n{integrated["report_text"]}")
                if integrated["report_stream"]:
                    yield integrated["report_stream"]
                    yield "\n\n"
            except Exception as e:
                logger.exception("Integrated analysis failed")
                yield f"⚠️ 分析过程出错: {e}\n\n"
                context_parts.append(f"## 分析过程异常\n{e}")

        # 5. 插入上下文系统消息（在用户消息之前），然后流式调用 LLM
        system_msg_content = None
        if context_parts:
            instructions = (
                "请严格依据以下知识库内容和用户记忆来回答问题。\n"
                "如果提供的参考信息与问题相关，请优先使用参考信息作答；"
                "如果参考信息不相关或不足，则忽略它们并基于自身知识正常回答。\n"
            )
            system_msg_content = instructions + "\n\n" + "\n\n".join(context_parts)

        multimodal_parts = _process_attachments(attachments)
        self.messages.append(Message(role="user", content=user_input, multimodal_parts=multimodal_parts))
        self.implicit_feedback.record_query(self.session_id, user_input, self.user_id)

        if system_msg_content:
            self.messages.insert(0, Message(role="system", content=system_msg_content))


        full_content = ""
        async for chunk in llm.stream_chat(self.messages):
            full_content += chunk
            yield chunk

        self.messages.append(Message(role="assistant", content=full_content))

        # 6. 记忆提取
        extraction_llm = await self._get_extraction_llm()
        if extraction_llm:
            await self._extract_and_store_memories(user_input, full_content)
    def load_history(self, messages: list[dict]) -> None:
        """Load historical messages into the agent's conversation context.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
        """
        from backend.models.base import Message as LLMMessage
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system", "tool"):
                self.messages.append(LLMMessage(role=role, content=content))

    # ═══════════════════════════ NL2Query 接口 ═══════════════════════════
    async def nl2query_code(self, query: str, data_type: str = "gnss", data_description: str = "",
                          file_id: str = "", data_schema: Optional[dict] = None) -> dict:
        from backend.analysis.codegen import generate_code
        return await generate_code(query, data_type, data_description, self.model_id, data_schema)
    async def nl2query_execute(self, query: str, data_type: str = "gnss", data_description: str = "",
                               file_id: str = "", use_cache: bool = True) -> dict:
        from backend.analysis.codegen import generate_code
        from backend.core.sandbox import CodeSandbox
        from backend.analysis.cache import QueryCache

        # Load data if a file was specified
        df = None
        data_schema = None
        sandbox_context = None
        if file_id:
            from backend.analysis.data_loader import load_data_for_analysis, dataframe_to_sandbox_context
            df, data_schema, err = load_data_for_analysis(file_id)
            if err:
                return {"success": False, "code": "", "result": {}, "error": f"数据读取失败: {err}"}
            if df is not None:
                sandbox_context = dataframe_to_sandbox_context(df)

        if use_cache and not sandbox_context:
            cache = QueryCache()
            cached = cache.get(query, data_type)
            if cached is not None:
                logger.info("NL2Query cache hit: %s...", query[:50])
                return {"success": True, "from_cache": True, "code": cached.get("code", ""), "result": cached.get("result", {})}
        gen_result = await self.nl2query_code(query, data_type, data_description, file_id, data_schema)
        if not gen_result["success"]:
            return gen_result
        code = gen_result["code"]
        sandbox = CodeSandbox(timeout=30)
        try:
            exec_result = sandbox.execute_python(code, context=sandbox_context)
            output = exec_result.to_dict()
            if use_cache and exec_result.success and not sandbox_context:
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
        except Exception as e:
            logger.warning("Knowledge base retrieval failed: %s", e)
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

    def set_react_max_iterations(self, n: int) -> None:
        """Set max ReAct loop iterations."""
        self._react_max_iterations = max(1, min(n, 50))

    def get_optimization_stats(self) -> dict:
        """Get complete self-growth optimization statistics."""
        memory_stats = {}
        try:
            mems = self.memory.get(user_id=self.user_id, top_k=1000)
            memory_stats = {
                "total_count": len(mems),
                "preference_count": sum(1 for m in mems if m.get("memory_type") == "preference"),
                "knowledge_count": sum(1 for m in mems if m.get("memory_type") == "knowledge"),
                "experience_count": sum(1 for m in mems if m.get("memory_type") == "experience"),
                "avg_weight": round(sum(m.get("weight", 1.0) for m in mems) / max(len(mems), 1), 2),
            }
        except Exception as e:
            memory_stats = {"error": str(e)}
        feedback_stats = {}
        try:
            feedback_stats = self.feedback_collector.get_stats()
        except Exception as e:
            feedback_stats = {"error": str(e)}
        prompt_stats = {}
        try:
            prompt_stats = {
                "analysis": self.prompt_optimizer.get_best_for_task("analysis"),
                "retrieval": self.prompt_optimizer.get_best_for_task("retrieval"),
                "report": self.prompt_optimizer.get_best_for_task("report"),
            }
        except Exception as e:
            prompt_stats = {"error": str(e)}
        finetune_stats = {}
        try:
            finetune_stats = {
                "models_count": len(self.fine_tuner.list_models()),
                "models": self.fine_tuner.list_models(),
            }
        except Exception as e:
            finetune_stats = {"error": str(e)}
        return {
            "user_id": self.user_id,
            "memory": memory_stats,
            "feedback": feedback_stats,
            "finetune": finetune_stats,
            "prompt": prompt_stats,
            "optimization_enabled": self._optimization_enabled,
        }

    def toggle_optimization(self, enabled=None):
        if enabled is not None:
            self._optimization_enabled = enabled
        else:
            self._optimization_enabled = not self._optimization_enabled
        return self._optimization_enabled

    # ============================================================
    # ReAct loop
    # ============================================================

    async def _react_tool_analyze(self, query: str, data_type: str = "gnss") -> str:
        """Execute NL2Query analysis and return observation."""
        try:
            import json
            result = await self.nl2query_execute(query=query, data_type=data_type, use_cache=True)
            if result.get("success"):
                res = result.get("result", {})
                parts = []
                stdout = res.get("stdout", "")
                if stdout:
                    parts.append("Output: " + stdout[:200])
                figures = res.get("figures", [])
                if figures:
                    parts.append("Generated " + str(len(figures)) + " charts")
                data = res.get("data", {})
                if data:
                    parts.append("Data: " + json.dumps(data, ensure_ascii=False)[:500])
                if res.get("execution_time_ms", 0) > 0:
                    parts.append("Time: " + str(int(res["execution_time_ms"])) + "ms")
                return "\n".join(parts) if parts else "Analysis complete"
            else:
                return "Analysis failed: " + result.get("error", "unknown error")
        except Exception as e:
            return "Tool error: " + str(e)

    async def _react_tool_search_knowledge(self, query: str) -> str:
        """Search vector knowledge base."""
        try:
            from backend.retrieval.vector_store import get_vector_store
            store = get_vector_store()
            results = await store.search(query, top_k=3)
            if not results:
                return "No relevant content found"
            lines = []
            for i, r in enumerate(results):
                lines.append("[Result " + str(i+1) + "] " + r["content"][:200])
            return "\n".join(lines)
        except Exception as e:
            return "Knowledge search error: " + str(e)

    async def _react_tool_search_memory(self, query: str) -> str:
        """Search long-term memory."""
        try:
            if not self._memory_enabled:
                return "Memory disabled"
            results = self.search_memories(query, top_k=5)
            if not results:
                return "No memories found"
            lines = []
            for m in results:
                mtype = m.get("memory_type", "unknown")
                key = m.get("key", "")
                value = m.get("value", "")[:200]
                weight = m.get("weight", 0)
                lines.append("[" + mtype + "] " + key + ": " + value + " (weight=" + str(round(weight, 2)) + ")")
            return "\n".join(lines)
        except Exception as e:
            return "Memory search error: " + str(e)

    async def _react_tool_generate_report(self, report_type: str, data: dict) -> str:
        """Generate monitoring report."""
        try:
            from backend.reporting.report_generator import ReportGenerator
            from datetime import datetime
            gen = ReportGenerator()
            data.setdefault("title", "Analysis Report")
            data.setdefault("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
            path = gen.generate(data, template=report_type, output_format="html")
            return "Report generated: " + str(path)
        except Exception as e:
            return "Report generation failed: " + str(e)

    async def _react_step(self, user_input: str, history: list) -> dict:
        """One ReAct iteration: think -> choose action."""
        try:
            llm = await self._get_llm()
        except Exception:
            return {"action": "final_answer", "action_input": {"answer": "No AI model available"}}
        if not llm:
            return {"action": "final_answer", "action_input": {"answer": "No AI model available"}}

        messages = [Message(role="system", content=REACT_SYSTEM_PROMPT)]
        for h in history:
            messages.append(Message(role=h["role"], content=h["content"]))
        messages.append(Message(role="user", content=user_input))

        try:
            response = await llm.chat(messages, temperature=0.3, max_tokens=2048)
            content = response.content.strip()
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content
            import json
            return json.loads(json_str)
        except Exception as e:
            return {"thought": "Parse error", "action": "final_answer", "action_input": {"answer": str(e)}}

    async def react_chat(self, user_input: str):
        """Full ReAct loop with think-act-observe iterations."""
        self._react_enabled = True
        self.messages.append(Message(role="user", content=user_input))
        memory_context = await self._recall_memories(user_input)
        rag_context = await self._retrieve_context(user_input)
        react_history = []
        if memory_context:
            react_history.append({"role": "system", "content": "[Memory]\n" + memory_context})
        if rag_context:
            react_history.append({"role": "system", "content": "[Knowledge]\n" + rag_context})
        yield "Starting ReAct analysis...\n\n"
        for iteration in range(self._react_max_iterations):
            step = await self._react_step(user_input, react_history)
            thought = step.get("thought", "")
            action = step.get("action", "final_answer")
            action_input = step.get("action_input", {})
            if thought:
                yield "Step " + str(iteration+1) + " - Thought: " + thought + "\n\n"
            if action == "final_answer":
                answer = action_input.get("answer", "")
                yield "Final answer:\n" + answer + "\n"
                self.messages.append(Message(role="assistant", content=answer))
                extraction_llm = await self._get_extraction_llm()
                if extraction_llm:
                    await self._extract_and_store_memories(user_input, answer)
                return
            elif action == "analyze_data":
                yield "Action: analyze data\n"
                observation = await self._react_tool_analyze(query=action_input.get("query", ""), data_type=action_input.get("data_type", "gnss"))
                yield "Observation:\n" + observation[:500] + "\n\n"
            elif action == "search_knowledge":
                yield "Action: search knowledge\n"
                observation = await self._react_tool_search_knowledge(query=action_input.get("query", ""))
                yield "Observation:\n" + observation[:500] + "\n\n"
            elif action == "search_memory":
                yield "Action: search memory\n"
                observation = await self._react_tool_search_memory(query=action_input.get("query", ""))
                yield "Observation:\n" + observation[:500] + "\n\n"
            elif action == "generate_report":
                yield "Action: generate report\n"
                observation = await self._react_tool_generate_report(report_type=action_input.get("report_type", "daily"), data=action_input.get("data", {}))
                yield "Observation: " + observation + "\n\n"
            else:
                yield "Unknown action: " + str(action) + "\n\n"
            import json
            react_history.append({"role": "assistant", "content": json.dumps(step, ensure_ascii=False)})
            react_history.append({"role": "system", "content": "Observation: " + observation})
        yield "Max iterations reached.\n"

    async def deploy_finetuned_model(self, model_name: str = "") -> str:
        """Deploy fine-tuned model to registry for inference."""
        try:
            model_id = await self.fine_tuner.deploy_to_registry(model_name=model_name)
            if model_id:
                return model_id
            return ""
        except Exception as e:
            return ""
