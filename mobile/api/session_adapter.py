"""Session adapter for mobile API - wraps backend session CRUD."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("research_agent.mobile.session_adapter")


def list_sessions(user_id: str = "default") -> list[dict]:
    """List sessions for a user, returning lightweight summaries."""
    from backend.db.session import sync_engine
    from sqlalchemy import text as sa_text

    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT id, title, model_id, created_at, updated_at, "
                    "(SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id) AS msg_count "
                    "FROM sessions WHERE user_id = :uid ORDER BY updated_at DESC LIMIT 50"
                ),
                {"uid": user_id},
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1] or "Untitled",
                    "model_id": r[2] or "default",
                    "created_at": str(r[3]) if r[3] else "",
                    "updated_at": str(r[4]) if r[4] else "",
                    "message_count": r[5] or 0,
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("Session list fallback (empty): %s", e)
        return []


def create_session(user_id: str = "default", title: str = "New Session",
                   model_id: Optional[str] = None) -> dict:
    """Create a new session and return its summary."""
    import uuid
    from backend.db.session import sync_engine
    from sqlalchemy import text as sa_text

    session_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                sa_text(
                    "INSERT INTO sessions (id, user_id, title, model_id, created_at, updated_at) "
                    "VALUES (:id, :uid, :title, :mid, :now, :now)"
                ),
                {
                    "id": session_id,
                    "uid": user_id,
                    "title": title[:100],
                    "mid": model_id or "default",
                    "now": now_iso,
                },
            )
    except Exception as e:
        logger.warning("Session create via SQL failed: %s, using local fallback", e)
        # fallback: return local session

    return {
        "id": session_id,
        "title": title[:100],
        "model_id": model_id or "default",
        "user_id": user_id,
        "created_at": now_iso,
        "updated_at": now_iso,
        "message_count": 0,
    }


def get_session_messages(session_id: str, limit: int = 50) -> list[dict]:
    """Get session messages, returning lightweight JSON."""
    from backend.db.session import sync_engine
    from sqlalchemy import text as sa_text

    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT id, role, content, created_at, metadata "
                    "FROM messages WHERE session_id = :sid "
                    "ORDER BY created_at ASC LIMIT :lim"
                ),
                {"sid": session_id, "lim": limit},
            ).fetchall()
            messages = []
            for r in rows:
                msg = {
                    "id": r[0],
                    "role": r[1],
                    "content": r[2][:500] if r[2] else "",
                    "created_at": str(r[3]) if r[3] else "",
                }
                messages.append(msg)
            return messages
    except Exception as e:
        logger.warning("Failed to fetch messages: %s", e)
        return []
