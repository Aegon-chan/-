"""REST API for API key configuration management."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.config import settings
from backend.db.crypto import encrypt, decrypt
from backend.schemas.config import ApiKeysStatusResponse, ApiKeysUpdateRequest

router = APIRouter()

# DB table name and column mapping
_TABLE = "config_store"
_DB_PATH = settings.database_url
_KEYS = {
    "deepseek": "deepseek_api_key",
    "kimi": "kimi_api_key",
    "openai": "openai_api_key",
}


def _get_db_path() -> str:
    """Extract SQLite file path from DATABASE_URL."""
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)"
    )
    conn.commit()


@router.get("/api-keys", response_model=ApiKeysStatusResponse)
async def get_api_keys_status():
    """Return which models have API keys configured."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        status = {}
        for model, col in _KEYS.items():
            row = conn.execute(
                f"SELECT value FROM {_TABLE} WHERE key = ?", (col,)
            ).fetchone()
            status[model] = row is not None and row[0] != ""
    finally:
        conn.close()
    return ApiKeysStatusResponse(**status)


@router.post("/api-keys", response_model=ApiKeysStatusResponse)
async def save_api_keys(body: ApiKeysUpdateRequest):
    """Save API keys, encrypting them before storage, then reload models."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        mapping = {
            "deepseek": body.deepseek_api_key,
            "kimi": body.kimi_api_key,
            "openai": body.openai_api_key,
        }
        now = datetime.now(timezone.utc).isoformat()
        for model, val in mapping.items():
            if val is not None and val.strip():
                encrypted = encrypt(val.strip())
                conn.execute(
                    f"INSERT OR REPLACE INTO {_TABLE} (key, value, updated_at) VALUES (?, ?, ?)",
                    (_KEYS[model], encrypted, now),
                )
            elif val is not None and val.strip() == "":
                # Explicitly delete key if empty string provided
                conn.execute(
                    f"DELETE FROM {_TABLE} WHERE key = ?", (_KEYS[model],)
                )
        conn.commit()
    finally:
        conn.close()

    # Hot-reload models with new keys
    from backend.models import reload_models
    reload_models()

    return await get_api_keys_status()


def load_decrypted_keys() -> dict[str, str]:
    """Load and decrypt API keys from DB. Returns {model_id: api_key}."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    result = {}
    try:
        _ensure_table(conn)
        for model, col in _KEYS.items():
            row = conn.execute(
                f"SELECT value FROM {_TABLE} WHERE key = ?", (col,)
            ).fetchone()
            if row and row[0]:
                try:
                    result[model] = decrypt(row[0])
                except Exception:
                    pass
    finally:
        conn.close()
    return result