"""
???????

??????????????????????????
???????????????????
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.memory")


class MemoryStore:
    """??????? SQLite ????????????????????"""

    def __init__(self, db_path: str = "./data/memories.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._start_decay_timer()

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

    # ?? ???? ??????????????????????????????????????????????????

    _decay_timer: Optional[threading.Timer] = None

    def _start_decay_timer(self, interval_hours: int = 6):
        """?????????? 6 ???????"""
        if self._decay_timer and self._decay_timer.is_alive():
            return

        def _run():
            self.decay_weights(factor=0.95)
            logger.info("Memory weights decayed (factor=0.95)")
            self._decay_timer = threading.Timer(interval_hours * 3600, _run)
            self._decay_timer.daemon = True
            self._decay_timer.start()

        self._decay_timer = threading.Timer(interval_hours * 3600, _run)
        self._decay_timer.daemon = True
        self._decay_timer.start()
        logger.info("Memory decay timer started (interval=%sh)", interval_hours)

    # ?? ?? CRUD ??????????????????????????????????????????????????

    def add(self, user_id: str, memory_type: str, key: str, value: str,
            weight: float = 1.0, source: str = "", metadata: dict = None) -> int:
        """?????????? key ????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            # ???????? key ???
            existing = conn.execute(
                "SELECT id, weight FROM memories WHERE user_id=? AND memory_type=? AND key=?",
                (user_id, memory_type, key),
            ).fetchone()
            if existing:
                # ?????????? value
                mem_id, old_weight = existing
                new_weight = min(old_weight + weight, 5.0)  # ?? 5.0
                conn.execute(
                    "UPDATE memories SET weight=?, value=?, updated_at=CURRENT_TIMESTAMP, metadata=? WHERE id=?",
                    (new_weight, value, json.dumps(metadata or {}), mem_id),
                )
                return mem_id
            cur = conn.execute(
                "INSERT INTO memories (user_id, memory_type, key, value, weight, source, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, memory_type, key, value, weight, source, json.dumps(metadata or {})),
            )
            return cur.lastrowid

    def get(self, user_id: str, memory_type: Optional[str] = None,
            top_k: int = 10) -> list[dict]:
        """??????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id=? AND memory_type=? "
                    "ORDER BY weight DESC LIMIT ?",
                    (user_id, memory_type, top_k),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE user_id=? "
                    "ORDER BY weight DESC LIMIT ?",
                    (user_id, top_k),
                ).fetchall()
            return [dict(r) for r in rows]

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        """????????key ? value ???"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id=? AND (key LIKE ? OR value LIKE ?) "
                "ORDER BY weight DESC LIMIT ?",
                (user_id, f"%{query}%", f"%{query}%", top_k),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_weight(self, memory_id: int, delta: float):
        """??????????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "UPDATE memories SET weight = MAX(weight + ?, 0.0), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (delta, memory_id),
            )

    def decay_weights(self, factor: float = 0.95):
        """??????????????????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET weight = weight * ?", (factor,))
            # ??????????< 0.1?
            conn.execute("DELETE FROM memories WHERE weight < 0.1")
            logger.debug("Memory decay: factor=%s, low-weight entries cleaned", factor)

    def get_stats(self, user_id: str) -> dict:
        """????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) as cnt, AVG(weight) as avg_w FROM memories WHERE user_id=? GROUP BY memory_type",
                (user_id,),
            ).fetchall()
            return {
                "total": total,
                "by_type": {r[0]: {"count": r[1], "avg_weight": round(r[2], 3)} for r in by_type},
            }

    def delete(self, memory_id: int):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def delete_by_type(self, user_id: str, memory_type: str):
        """????????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM memories WHERE user_id=? AND memory_type=?",
                (user_id, memory_type),
            )

    def __del__(self):
        if self._decay_timer and self._decay_timer.is_alive():
            self._decay_timer.cancel()
