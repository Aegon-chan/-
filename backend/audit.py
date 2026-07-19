"""Audit logging module.

Records all non-GET API calls to a structured SQLite audit log
for security review and operational transparency.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Request, Response

logger = logging.getLogger("research_agent.audit")


class _AuditDB:
    """SQLite-backed audit log store."""

    def __init__(self, db_path: str = "./data/audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status_code INTEGER,
                    duration_ms REAL,
                    user_agent TEXT DEFAULT '',
                    client_host TEXT DEFAULT '',
                    request_summary TEXT DEFAULT '',
                    error TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_method
                ON audit_log(method)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_path
                ON audit_log(path)
            """)

    def write(self, record: dict) -> str:
        import sqlite3
        record.setdefault("id", str(uuid.uuid4()))
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO audit_log
                    (id, timestamp, method, path, status_code, duration_ms,
                     user_agent, client_host, request_summary, error)
                VALUES
                    (:id, :timestamp, :method, :path, :status_code, :duration_ms,
                     :user_agent, :client_host, :request_summary, :error)
            """, record)
        return record["id"]

    def query(self, limit: int = 100, offset: int = 0,
              method: str = "", path: str = "", status_min: int = 0) -> list[dict]:
        import sqlite3
        conditions = []
        params = {"limit": limit, "offset": offset}
        if method:
            conditions.append("method = :method")
            params["method"] = method.upper()
        if path:
            conditions.append("path LIKE :path")
            params["path"] = f"%{path}%"
        if status_min:
            conditions.append("status_code >= :status_min")
            params["status_min"] = status_min
        where = " AND ".join(conditions) if conditions else "1=1"
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"""
                SELECT * FROM audit_log
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """, params).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict:
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            by_method = {
                r["method"]: r["cnt"]
                for r in conn.execute(
                    "SELECT method, COUNT(*) as cnt FROM audit_log GROUP BY method"
                ).fetchall()
            }
            errors = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE status_code >= 500"
            ).fetchone()[0]
            return {
                "total_entries": total,
                "by_method": by_method,
                "error_count": errors,
            }

    def cleanup(self, keep_days: int = 90):
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM audit_log WHERE timestamp < date('now', :days)",
                {"days": f"-{keep_days} days"},
            )


_audit_db: Optional[_AuditDB] = None


def get_audit_db() -> _AuditDB:
    global _audit_db
    if _audit_db is None:
        _audit_db = _AuditDB()
    return _audit_db


async def audit_middleware(request: Request, call_next):
    """FastAPI middleware that logs all non-healthcheck API calls."""
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
        status = response.status_code
        error = ""
    except Exception as exc:
        status = 500
        error = str(exc)[:200]
        raise
    finally:
        duration = (time.perf_counter() - start) * 1000
        method = request.method
        path = request.url.path

        # Skip healthcheck and static files
        if path not in ("/health", "/metrics") and not path.startswith("/uploads"):
            # Only log mutations (POST/PUT/DELETE) + errors
            if method in ("POST", "PUT", "DELETE") or status >= 400:
                try:
                    db = get_audit_db()
                    db.write({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "method": method,
                        "path": path,
                        "status_code": status,
                        "duration_ms": round(duration, 1),
                        "user_agent": request.headers.get("user-agent", "")[:200],
                        "client_host": request.client.host if request.client else "",
                        "request_summary": "",
                        "error": error,
                    })
                except Exception as e:
                    logger.warning("Audit write failed: %s", e)

    return response  # type: ignore[return-value]
