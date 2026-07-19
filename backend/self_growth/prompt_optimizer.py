"""Prompt auto-optimization module (APE + version management)."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.prompt")


class PromptOptimizer:
    """Prompt optimizer with APE, version management, and template library."""

    def __init__(self, db_path: str = "./data/prompts.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    content TEXT NOT NULL,
                    score REAL DEFAULT 0.0,
                    parent_version INTEGER DEFAULT 0,
                    test_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_type
                ON prompt_templates(task_type, version DESC)
            """)

    def get_template(self, task_type: str, version: Optional[int] = None) -> Optional[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if version:
                row = conn.execute(
                    "SELECT * FROM prompt_templates WHERE task_type=? AND version=?",
                    (task_type, version),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM prompt_templates WHERE task_type=? ORDER BY score DESC, version DESC LIMIT 1",
                    (task_type,),
                ).fetchone()
            return dict(row) if row else None

    def save_template(self, task_type: str, content: str, parent_version: int = 0) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            last = conn.execute(
                "SELECT MAX(version) FROM prompt_templates WHERE task_type=?", (task_type,)
            ).fetchone()[0]
            version = (last or 0) + 1
            conn.execute(
                "INSERT INTO prompt_templates (task_type, version, content, parent_version) VALUES (?, ?, ?, ?)",
                (task_type, version, content, parent_version),
            )
            logger.info("Prompt saved: %s v%d", task_type, version)
            return version

    def list_versions(self, task_type: str) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM prompt_templates WHERE task_type=? ORDER BY version DESC",
                (task_type,),
            ).fetchall()
            return [dict(r) for r in rows]

    async def optimize(self, task_type: str, feedback_data: list) -> str:
        """Optimize prompt using APE method based on feedback data."""
        if not feedback_data:
            current = self.get_template(task_type)
            return current["content"] if current else ""

        from backend.models.registry import ModelRegistry
        from backend.models.base import Message

        current = self.get_template(task_type)
        current_content = current["content"] if current else "unset"

        feedback_lines = []
        for f in feedback_data[-20:]:
            rating = f.get("rating", 0)
            comment = str(f.get("comment", ""))[:100]
            feedback_lines.append("- rating " + str(rating) + ": " + comment)
        feedback_str = "\n".join(feedback_lines)

        optimize_prompt = (
            "You are a prompt engineering expert. Based on the current prompt and user feedback, "
            "generate an optimized version.\n\n"
            "Current prompt (" + task_type + "):\n---\n" + current_content + "\n---\n\n"
            "Recent feedback:\n" + (feedback_str or "none") + "\n\n"
            "Requirements:\n"
            "1. Keep core functionality unchanged\n"
            "2. Address issues mentioned in feedback\n"
            "3. Make instructions clearer and more specific\n"
            "4. Only output the optimized prompt content\n"
        )

        try:
            llm = ModelRegistry.get_llm_with_fallback()
            if not llm:
                return current_content

            response = await llm.chat([Message(role="user", content=optimize_prompt)],
                                       temperature=0.7, max_tokens=2000)
            new_content = response.content.strip()

            if new_content and len(new_content) > 50:
                parent_v = current["version"] if current else 0
                self.save_template(task_type, new_content, parent_version=parent_v)
                logger.info("APE: optimized %s prompt (v%d -> v%d)", task_type, parent_v, parent_v + 1)
                return new_content

            return current_content
        except Exception as e:
            logger.error("Prompt optimization failed: %s", e)
            return current_content

# ═══════════════════════════ APE 搜索算法 ═══════════════════════════

    async def ape_search(self, task_type: str, candidate_prompts: list[str],
                         eval_fn, population_size: int = 5,
                         generations: int = 3, mutation_rate: float = 0.3) -> str:
        """Automatic Prompt Engineering via evolutionary search."""
        import random

        current = self.get_template(task_type)
        if current and current["content"] not in candidate_prompts:
            candidate_prompts.insert(0, current["content"])

        pool = candidate_prompts[:population_size]
        best_prompt = pool[0]
        best_score = 0.0

        for gen in range(generations):
            scored = []
            for prompt in pool:
                try:
                    result = await eval_fn(prompt)
                    score = result.get("score", 0.0)
                except Exception as e:
                    logger.warning("APE eval failed for prompt: %s", e)
                    score = 0.0
                scored.append((prompt, score))

            scored.sort(key=lambda x: x[1], reverse=True)

            if scored and scored[0][1] > best_score:
                best_prompt = scored[0][0]
                best_score = scored[0][1]
                parent_v = current["version"] if current else 0
                self.save_template(task_type, best_prompt, parent_version=parent_v)
                logger.info("APE gen %d: new best score=%.3f for %s", gen, best_score, task_type)

            top = [s[0] for s in scored[:max(2, population_size // 2)]]
            pool = list(top)
            while len(pool) < population_size:
                parent = random.choice(top)
                child = await self._mutate_prompt(parent, mutation_rate)
                pool.append(child)

        return best_prompt

    async def _mutate_prompt(self, prompt: str, rate: float = 0.3) -> str:
        """Generate a mutated variant of a prompt using LLM or local heuristics."""
        import random
        from backend.models.registry import ModelRegistry
        from backend.models.base import Message

        if len(prompt) < 200 or random.random() < 0.3:
            lines = prompt.split(chr(10))
            if random.random() < rate and len(lines) > 3:
                idx = random.randint(0, len(lines) - 1)
                if lines[idx].strip() and not lines[idx].strip().startswith("##"):
                    words = lines[idx].split()
                    if len(words) > 3:
                        i = random.randint(0, len(words) - 2)
                        words[i], words[i + 1] = words[i + 1], words[i]
                        lines[idx] = " ".join(words)
            mutated = chr(10).join(lines)
            if mutated != prompt:
                return mutated

        mutation_prompt = (
            "You are a prompt engineer. Rewrite the following prompt to create "
            "a variant that might perform better. Keep the core instructions "
            "but change the phrasing, structure, or emphasis."
            + chr(10) + chr(10) + "Original prompt:" + chr(10) + "---" + chr(10) + prompt + chr(10) + "---" + chr(10) + chr(10)
            + "Only output the rewritten prompt, no explanation."
        )
        try:
            llm = ModelRegistry.get_llm_with_fallback()
            if llm:
                resp = await llm.chat([Message(role="user", content=mutation_prompt)],
                                       temperature=0.8, max_tokens=2000)
                mutated = resp.content.strip()
                if mutated and len(mutated) > 50:
                    return mutated
        except Exception as e:
            logger.warning("APE mutation via LLM failed: %s", e)

        return prompt

    def _regression_check(self, new_prompt: str, task_type: str,
                          known_bad_cases: list[dict]) -> dict:
        if not known_bad_cases:
            return {"passed": True, "failed_cases": []}

        failed = []
        for case in known_bad_cases:
            inp = case.get("input", "")
            expected = case.get("expected_output", "")
            if expected and inp:
                prompt_lower = new_prompt.lower()
                key_terms = [w for w in expected.lower().split() if len(w) > 3]
                missing = [t for t in key_terms if t not in prompt_lower]
                if len(missing) > len(key_terms) * 0.5:
                    failed.append({"input": inp, "missing_terms": missing})

        return {"passed": len(failed) == 0, "failed_cases": failed}

    async def ab_test(self, task_type: str, prompt_a: str, prompt_b: str,
                      test_inputs: list[str], eval_fn) -> dict:
        scores_a = []
        scores_b = []
        for inp in test_inputs:
            try:
                ra = await eval_fn(prompt_a, inp)
                rb = await eval_fn(prompt_b, inp)
                scores_a.append(ra.get("score", 0))
                scores_b.append(rb.get("score", 0))
            except Exception as e:
                logger.warning("A/B test eval failed for input: %s", e)

        if not scores_a or not scores_b:
            return {"winner": "unknown", "score_a": 0, "score_b": 0, "improvement": 0}

        avg_a = sum(scores_a) / len(scores_a)
        avg_b = sum(scores_b) / len(scores_b)
        improvement = avg_b - avg_a

        winner = "a" if avg_a >= avg_b else "b"
        self.save_template(f"{task_type}_ab_a", prompt_a)
        self.save_template(f"{task_type}_ab_b", prompt_b)

        logger.info("A/B test [%s]: A=%.3f B=%.3f winner=%s improvement=%.3f",
                     task_type, avg_a, avg_b, winner, improvement)
        return {
            "winner": winner,
            "score_a": round(avg_a, 4),
            "score_b": round(avg_b, 4),
            "improvement": round(improvement, 4),
        }
# ═══════════════════════════ 新 API 别名 ═══════════════════════════

    def get_best_for_task(self, task_type: str) -> Optional[dict]:
        """获取指定任务类型当前评分最高的 prompt 模板。

        等价于 get_template(task_type)，提供更清晰的命名。
        """
        return self.get_template(task_type)

    async def auto_optimize(self, task_type: str, feedback_content: dict,
                            rating: int) -> Optional[str]:
        """基于单条高质量反馈的自动 Prompt 优化。

        当 rating >= 3 时，将该反馈作为正样本，调用 APE 优化主循环
        生成新的 prompt 变体。

        Args:
            task_type: 任务类型
            feedback_content: 包含 comment, tags 等字段的反馈字典
            rating: 评分 (1-5)

        Returns:
            优化后的 prompt 内容，若未优化则返回 None
        """
        if rating < 3:
            return None

        feedbacks = [{
            "rating": rating,
            "comment": str(feedback_content.get("comment", "")),
            "tags": feedback_content.get("tags", []),
            "content": str(feedback_content.get("content", "")),
        }]

        content = await self.optimize(task_type, feedbacks)
        return content if content else None

