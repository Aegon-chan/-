"""Query cache module.

Caches NL query execution results to avoid redundant computation
and LLM calls. Uses SQLite for persistence.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("research_agent.cache")


class QueryCache:
    """SQLite-backed cache for NL query results."""

    def __init__(self, db_path: str = "./data/query_cache.db", ttl_hours: int = 24):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    code TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_query
                ON query_cache(query, data_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_created
                ON query_cache(created_at)
            """)

    def _make_key(self, query: str, data_type: str, code: str = "") -> str:
        """Generate a deterministic cache key."""
        raw = f"{query}:{data_type}:{code}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:32]

    def get(self, query: str, data_type: str, code: str = "") -> Optional[dict]:
        """Retrieve cached result. Returns None if expired or missing."""
        key = self._make_key(query, data_type, code)
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT result, created_at FROM query_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()

        if row is None:
            return None

        result_json, created_at_str = row
        created_at = datetime.fromisoformat(created_at_str)

        # Check TTL
        if datetime.utcnow() - created_at > timedelta(hours=self.ttl_hours):
            self.delete(key)
            return None

        # Update access count
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "UPDATE query_cache SET access_count = access_count + 1 WHERE cache_key = ?",
                (key,),
            )

        return json.loads(result_json)

    def set(self, query: str, data_type: str, code: str, result: dict) -> str:
        """Store a query result in cache."""
        key = self._make_key(query, data_type, code)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO query_cache
                   (cache_key, query, data_type, code, result, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, query[:500], data_type, code[:2000],
                 json.dumps(result, default=str),
                 datetime.utcnow().isoformat()),
            )
        return key

    def delete(self, key: str):
        """Delete a cache entry."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))

    def clear_expired(self):
        """Remove all expired entries."""
        cutoff = (datetime.utcnow() - timedelta(hours=self.ttl_hours)).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM query_cache WHERE created_at < ?", (cutoff,))

    def list_recent(self, limit: int = 20) -> list[dict]:
        """List recent cache entries."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """SELECT cache_key, query, data_type, created_at, access_count
                   FROM query_cache ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()

        return [
            {
                "key": r[0],
                "query": r[1],
                "data_type": r[2],
                "created_at": r[3],
                "access_count": r[4],
            }
            for r in rows
        ]
