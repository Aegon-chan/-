"""Prompt auto-optimization module (APE + version management)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
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
            cur = conn.execute(
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