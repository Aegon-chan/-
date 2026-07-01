"""Implicit feedback tracking module.

Records user interaction patterns as implicit feedback signals:
- Repeated queries (same or very similar query within a session)
- Quick topic switches (abrupt change in topic within short time)
- Message editing (user edits their own message before assistant responds)
- Rapid re-querying (asking the same question again after getting an answer)
- Scroll-back (user scrolls back to re-read old messages)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.implicit_feedback")


class ImplicitFeedbackCollector:
    """Collects and stores implicit feedback signals from user interactions."""

    def __init__(self, db_path: str = "./data/feedback.db",
                 similarity_threshold: float = 0.85,
                 topic_switch_window_s: int = 30,
                 enable: bool = True):
        self.db_path = Path(db_path)
        self.similarity_threshold = similarity_threshold
        self.topic_switch_window_s = topic_switch_window_s
        self.enable = enable

        # In-memory tracking per session
        self._session_history: dict[str, list[dict]] = defaultdict(list)
        self._session_stats: dict[str, dict] = defaultdict(lambda: {
            "query_count": 0,
            "repeated_queries": 0,
            "topic_switches": 0,
            "edits": 0,
            "rapid_requeries": 0,
            "last_query_time": 0.0,
            "last_query_text": "",
        })

    def record_query(self, session_id: str, query: str, user_id: str = "default") -> dict:
        """Record a user query and detect implicit feedback signals.

        Returns a dict of detected signals (empty dict if none detected or disabled).
        """
        if not self.enable:
            return {}

        signals = {}
        stats = self._session_stats[session_id]
        history = self._session_history[session_id]

        now = time.time()

        # Signal 1: Repeated query (same/similar to a previous one)
        if stats["query_count"] > 0 and query:
            for prev in history:
                prev_query = prev.get("query", "")
                if prev_query:
                    similarity = SequenceMatcher(None, query.lower(), prev_query.lower()).ratio()
                    if similarity >= self.similarity_threshold:
                        signals["repeated_query"] = {
                            "original_query": prev_query,
                            "similarity": round(similarity, 3),
                            "time_delta_s": round(now - prev.get("timestamp", now), 1),
                        }
                        stats["repeated_queries"] += 1
                        break

        # Signal 2: Rapid re-query (same topic, very short interval)
        if stats["last_query_time"] > 0 and query:
            time_delta = now - stats["last_query_time"]
            if time_delta < self.topic_switch_window_s and time_delta >= 0:
                similarity = SequenceMatcher(None, query.lower(),
                                              stats["last_query_text"].lower()).ratio()
                if similarity > 0.5:
                    signals["rapid_requery"] = {
                        "time_delta_s": round(time_delta, 1),
                        "similarity": round(similarity, 3),
                    }
                    stats["rapid_requeries"] += 1

        # Signal 3: Topic switch (different query shortly after previous)
        if stats["last_query_time"] > 0 and query:
            time_delta = now - stats["last_query_time"]
            if time_delta < self.topic_switch_window_s and time_delta >= 0:
                similarity = SequenceMatcher(None, query.lower(),
                                              stats["last_query_text"].lower()).ratio()
                if similarity < 0.3:
                    signals["topic_switch"] = {
                        "time_delta_s": round(time_delta, 1),
                        "similarity": round(similarity, 3),
                    }
                    stats["topic_switches"] += 1

        # Update history
        history.append({"query": query, "timestamp": now})
        stats["query_count"] += 1
        stats["last_query_time"] = now
        stats["last_query_text"] = query

        # Store signals in DB if any
        if signals:
            self._store_signals(session_id, user_id, query, signals)

        return signals

    def record_edit(self, session_id: str, original_query: str,
                    edited_query: str, user_id: str = "default") -> dict:
        """Record a user message edit."""
        if not self.enable:
            return {}

        similarity = SequenceMatcher(None, original_query.lower(), edited_query.lower()).ratio()
        if similarity > 0.99:
            return {}

        signal = {
            "edit": {
                "original_length": len(original_query),
                "edited_length": len(edited_query),
                "similarity": round(similarity, 3),
                "change_type": "minor" if similarity > 0.7 else "major",
            }
        }
        stats = self._session_stats[session_id]
        stats["edits"] += 1

        self._store_signals(session_id, user_id, edited_query, signal)
        return signal

    def get_session_signals(self, session_id: str) -> dict:
        """Get aggregated implicit feedback signals for a session."""
        return dict(self._session_stats.get(session_id, {}))

    def get_session_summary(self, session_id: str) -> dict:
        """Get a human-readable summary of detected signals."""
        stats = self._session_stats.get(session_id, {})
        total_signals = (stats.get("repeated_queries", 0) +
                         stats.get("topic_switches", 0) +
                         stats.get("edits", 0) +
                         stats.get("rapid_requeries", 0))

        return {
            "session_id": session_id,
            "total_queries": stats.get("query_count", 0),
            "total_signals": total_signals,
            "repeated_queries": stats.get("repeated_queries", 0),
            "topic_switches": stats.get("topic_switches", 0),
            "edits": stats.get("edits", 0),
            "rapid_requeries": stats.get("rapid_requeries", 0),
            "implicit_feedback_quality": (
                "high" if total_signals > 10 else
                "medium" if total_signals > 3 else
                "low"
            ),
        }

    def _store_signals(self, session_id: str, user_id: str,
                       query: str, signals: dict) -> None:
        """Store implicit feedback signals in the feedback database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                for signal_type, signal_data in signals.items():
                    rating = self._signal_to_rating(signal_type)
                    comment = json.dumps(signal_data, ensure_ascii=False)
                    metadata = json.dumps({
                        "source": "implicit",
                        "signal_type": signal_type,
                        "signal_data": signal_data,
                        "query": query[:500],
                    }, ensure_ascii=False)

                    conn.execute(
                        "INSERT INTO feedback (message_id, session_id, user_id, rating, comment, tags, metadata) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            f"implicit_{session_id}_{int(time.time()*1000)}",
                            session_id,
                            user_id,
                            rating,
                            comment[:500],
                            json.dumps([signal_type, "implicit"], ensure_ascii=False),
                            metadata,
                        ),
                    )
        except Exception as e:
            logger.warning("Failed to store implicit feedback: %s", e)

    @staticmethod
    def _signal_to_rating(signal_type: str) -> int:
        """Map signal type to a numerical rating."""
        mapping = {
            "repeated_query": -1,    # User had to ask again - possible dissatisfaction
            "rapid_requery": -2,     # User re-asked quickly - likely confused
            "topic_switch": 0,       # Neutral - user changed topic
            "edit_minor": 1,         # Minor edit - small correction
            "edit_major": -1,        # Major edit - significant correction
        }
        return mapping.get(signal_type, 0)

    def reset_session(self, session_id: str) -> None:
        """Reset tracking for a session."""
        self._session_history.pop(session_id, None)
        self._session_stats.pop(session_id, None)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable implicit feedback collection."""
        self.enable = enabled
        logger.info("Implicit feedback collection %s", "enabled" if enabled else "disabled")
