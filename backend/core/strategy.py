"""
??????

????????????????????
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.strategy")


class StrategyLibrary:
    """??????????????????"""

    def __init__(self, db_path: str = "./data/strategies.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    query TEXT NOT NULL,
                    data_type TEXT DEFAULT '',
                    steps TEXT NOT NULL,
                    result_summary TEXT DEFAULT '',
                    success_weight REAL DEFAULT 1.0,
                    execution_time_ms REAL DEFAULT 0,
                    user_id TEXT DEFAULT 'default',
                    tags TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    use_count INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategies_type
                ON strategies(task_type, data_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategies_weight
                ON strategies(success_weight DESC)
            """)

    def save(self, task_type: str, query: str, steps: list[dict],
             result_summary: str = "", data_type: str = "",
             execution_time_ms: float = 0.0, user_id: str = "default") -> int:
        """????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO strategies (task_type, query, data_type, steps, result_summary, execution_time_ms, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_type, query[:500], data_type, json.dumps(steps),
                 result_summary[:500], execution_time_ms, user_id),
            )
            logger.info("Strategy saved: %s [%s]", task_type, query[:50])
            return cur.lastrowid

    def search(self, query: str, task_type: str = "",
               data_type: str = "", top_k: int = 5) -> list[dict]:
        """??????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conditions = []
            params = []
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if data_type:
                conditions.append("data_type = ?")
                params.append(data_type)
            if query:
                conditions.append("(query LIKE ? OR tags LIKE ?)")
                params.append(f"%{query}%")
                params.append(f"%{query}%")
            where = " AND ".join(conditions) if conditions else "1=1"
            rows = conn.execute(
                f"SELECT * FROM strategies WHERE {where} ORDER BY success_weight DESC, use_count DESC LIMIT ?",
                params + [top_k],
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["steps"] = json.loads(d["steps"])
                d["tags"] = json.loads(d["tags"])
                results.append(d)
            return results

    def record_use(self, strategy_id: int, success: bool = True):
        """????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            delta = 0.1 if success else -0.2
            conn.execute(
                "UPDATE strategies SET use_count = use_count + 1, "
                "success_weight = MAX(success_weight + ?, 0.0), "
                "last_used = CURRENT_TIMESTAMP WHERE id = ?",
                (delta, strategy_id),
            )

    def get_top(self, task_type: str, top_k: int = 10) -> list[dict]:
        """????????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM strategies WHERE task_type=? ORDER BY success_weight DESC, use_count DESC LIMIT ?",
                (task_type, top_k),
            ).fetchall()
            return [dict(r) for r in rows]
