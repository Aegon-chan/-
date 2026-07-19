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
from datetime import datetime
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
# ═══════════════════════════ 反馈记忆集成 ═══════════════════════════

    def store_feedback_memory(self, user_id: str, feedback_data: dict) -> list[int]:
        """从反馈数据中提取并存储记忆。

        将反馈内容（评论/标签/上下文）解析为偏好、知识、经验类记忆，
        存入对应用户的记忆库。

        Args:
            user_id: 用户 ID
            feedback_data: 反馈数据字典，含 comment, tags, rating, content 等字段

        Returns:
            创建的 memory id 列表
        """
        memory_ids = []
        comment = str(feedback_data.get("comment", "")).strip()
        tags = feedback_data.get("tags", [])
        content = str(feedback_data.get("content", "")).strip()
        rating = feedback_data.get("rating", 0)

        if not comment and not tags and not content:
            return memory_ids

        # 从评论中提取关键信息作为知识
        if comment and len(comment) > 3:
            mid = self.add(
                user_id=user_id,
                memory_type="knowledge",
                key=f"feedback_comment_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                value=comment,
                weight=min(max(0.3, abs(rating) / 5.0), 1.0),
                source="feedback",
                metadata={"rating": rating, "type": "comment"},
            )
            memory_ids.append(mid)

        # 从标签中提取偏好
        valid_tags = [t for t in tags if isinstance(t, str) and len(t) > 1]
        for tag in valid_tags:
            mid = self.add(
                user_id=user_id,
                memory_type="preference",
                key=f"tag_{tag}",
                value=f"用户关注标签: {tag}",
                weight=0.6,
                source="feedback_tag",
                metadata={"rating": rating, "tag": tag},
            )
            memory_ids.append(mid)

        # 根据评分存储经验
        if rating >= 4:
            if content:
                mid = self.add(
                    user_id=user_id,
                    memory_type="experience",
                    key=f"high_rating_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    value=f"优质反馈: {content[:200]}",
                    weight=0.8,
                    source="feedback_high_rating",
                    metadata={"rating": rating},
                )
                memory_ids.append(mid)

        return memory_ids

    def get_relevant(self, user_id: str, query: str, memory_types: Optional[list] = None,
                     top_k: int = 10) -> list[dict]:
        """组合检索：关键词搜索 + 类型过滤，返回综合排序的记忆列表。

        Args:
            user_id: 用户 ID
            query: 检索关键词
            memory_types: 限定的记忆类型列表 (如 ['preference', 'knowledge'])
            top_k: 返回最大条数

        Returns:
            按权重降序排列的记忆列表
        """
        # 并行搜索关键词 + 按类型获取
        keyword_results = self.search(user_id, query, top_k=top_k)

        type_results = []
        if memory_types:
            for mtype in memory_types:
                type_results.extend(self.get(user_id, memory_type=mtype, top_k=top_k))
        else:
            type_results = self.get(user_id, top_k=top_k)

        # 合并去重（by key）
        seen_keys = set()
        combined = []
        for item in keyword_results + type_results:
            key = item.get("key", "")
            if key and key not in seen_keys:
                seen_keys.add(key)
                combined.append(item)

        # 按权重降序
        combined.sort(key=lambda x: x.get("weight", 0), reverse=True)
        return combined[:top_k]

