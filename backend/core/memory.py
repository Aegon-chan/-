"""
记忆管理系统。

管理短期记忆（对话上下文）和长期记忆（持久化知识）。
支持记忆权重、时效衰减和用户反馈修正。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class MemoryStore:
    """记忆存储：基于 SQLite 的持久化记忆系统"""

    def __init__(self, db_path: str = "./data/memories.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT '',
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    source TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_user_type
                ON memories(user_id, memory_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_weight
                ON memories(weight DESC)
            """)

    def add(self, user_id: str, memory_type: str, key: str, value: str,
            weight: float = 1.0, source: str = "", metadata: dict = None) -> int:
        """添加一条记忆"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO memories (user_id, memory_type, key, value, weight, source, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, memory_type, key, value, weight, source, json.dumps(metadata or {}))
            )
            return cur.lastrowid

    def get(self, user_id: str, memory_type: Optional[str] = None,
            top_k: int = 10) -> list[dict]:
        """获取记忆，按权重排序"""
        with sqlite3.connect(str(self.db_path)) as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id=? AND memory_type=? "
                    "ORDER BY weight DESC LIMIT ?",
                    (user_id, memory_type, top_k)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id=? "
                    "ORDER BY weight DESC LIMIT ?",
                    (user_id, top_k)
                ).fetchall()
            return [dict(r) for r in rows]

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        """关键词搜索记忆"""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id=? AND (key LIKE ? OR value LIKE ?) "
                "ORDER BY weight DESC LIMIT ?",
                (user_id, f"%{query}%", f"%{query}%", top_k)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_weight(self, memory_id: int, delta: float):
        """更新记忆权重（用户反馈驱动）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "UPDATE memories SET weight = weight + ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (delta, memory_id)
            )

    def decay_weights(self, factor: float = 0.95):
        """对所有记忆权重施加时效衰减"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET weight = weight * ?", (factor,))

    def delete(self, memory_id: int):
        """删除记忆"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
