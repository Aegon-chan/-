"""?????????

???????????/??/??/????????????????????
???????????????????????
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.feedback")


class FeedbackCollector:
    """???????????????????"""

    def __init__(self, db_path: str = "./data/feedback.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    session_id TEXT DEFAULT '',
                    user_id TEXT DEFAULT 'default',
                    rating INTEGER DEFAULT 0,
                    comment TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS implicit_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    event_type TEXT NOT NULL,
                    event_data TEXT DEFAULT '{}',
                    session_id TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_message
                ON feedback(message_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON feedback(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_implicit_user
                ON implicit_feedback(user_id)
            """)

    # ?? ???? ??????????????????????????????????????????????????

    def collect(self, message_id: str, rating: int, comment: str = "",
                tags: list = None, user_id: str = "default",
                session_id: str = "") -> dict:
        """????????

        Parameters
        ----------
        message_id : str
            ?????? ID
        rating : int
            ??: 1 (?/??), -1 (?/??), 2-5 (????)
        comment : str
            ????
        tags : list
            ?????? ["??", "??", "???"]
        user_id : str
            ?? ID
        session_id : str
            ?? ID

        Returns
        -------
        dict : {id, message_id, rating, comment}
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO feedback (message_id, session_id, user_id, rating, comment, tags) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, session_id, user_id, rating, comment, json.dumps(tags or [])),
            )
            feedback_id = cur.lastrowid
            logger.info("Feedback collected: msg=%s rating=%d", message_id, rating)
            return {
                "id": feedback_id,
                "message_id": message_id,
                "rating": rating,
                "comment": comment,
                "tags": tags or [],
            }

    def get_feedback_by_message(self, message_id: str) -> Optional[dict]:
        """?????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM feedback WHERE message_id=? ORDER BY created_at DESC LIMIT 1",
                (message_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_feedback_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        """?????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            positive = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating > 0").fetchone()[0]
            negative = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating < 0").fetchone()[0]
            with_comment = conn.execute("SELECT COUNT(*) FROM feedback WHERE comment != ''").fetchone()[0]
            high_quality = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating >= 3").fetchone()[0]
            return {
                "total": total,
                "positive": positive,
                "negative": negative,
                "with_comment": with_comment,
                "high_quality_count": high_quality,
            }

    # ?? ???? ??????????????????????????????????????????????????

    def log_implicit(self, user_id: str, event_type: str, event_data: dict = None,
                     session_id: str = "") -> int:
        """????????

        event_type ??:
        - "message_edited" ? ???????
        - "query_repeated" ? ???????
        - "session_continued" ? ????????
        - "feature_used" ? ????????? (NL2Query/????/??)
        - "copy_result" ? ?????????
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO implicit_feedback (user_id, event_type, event_data, session_id) "
                "VALUES (?, ?, ?, ?)",
                (user_id, event_type, json.dumps(event_data or {}), session_id),
            )
            return cur.lastrowid

    def get_implicit_events(self, user_id: str, event_type: Optional[str] = None,
                            limit: int = 50) -> list[dict]:
        """????????"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM implicit_feedback WHERE user_id=? AND event_type=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM implicit_feedback WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    # ?? ?????? ?????????????????????????????????????????????

    def to_training_data(self, min_rating: int = 1, include_sessions: bool = True) -> list[dict]:
        """?????????????????

        Parameters
        ----------
        min_rating : int
            ????????? 1???/???
        include_sessions : bool
            ?????????

        Returns
        -------
        list[dict] : ???? instruction, input, output
        """
        records = []
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback WHERE rating >= ? ORDER BY created_at DESC",
                (min_rating,),
            ).fetchall()

        for row in rows:
            record = {
                "feedback_id": row["id"],
                "message_id": row["message_id"],
                "rating": row["rating"],
                "comment": row["comment"],
                "tags": json.loads(row["tags"]),
                "session_id": row["session_id"],
            }
            records.append(record)

        return records

    def export_for_finetune(self, output_path: str, min_rating: int = 1) -> int:
        """??? HuggingFace datasets ??? JSONL ??"""
        records = self.to_training_data(min_rating)
        if not records:
            logger.warning("No training data to export (min_rating=%s)", min_rating)
            return 0

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        logger.info("Exported %d training samples to %s", len(records), out)
        return len(records)
