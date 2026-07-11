"""Shared test fixtures and configuration."""
from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from sqlalchemy import select


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables and seed test user before any test runs."""
    from backend.db.session import sync_engine, SyncSessionLocal
    from backend.db.models import Base, User
    Base.metadata.create_all(bind=sync_engine)
    with SyncSessionLocal() as session:
        existing = session.execute(
            select(User).where(User.id == "test-user")
        ).scalar_one_or_none()
        if not existing:
            session.add(User(id="test-user", username="test-user", display_name="Test User"))
            session.commit()
    yield
    Base.metadata.drop_all(bind=sync_engine)


# ── Test environment ────────────────────────────────────────────────

os.environ["APP_ENV"] = "development"
os.environ["APP_DEBUG"] = "false"
os.environ["DEEPSEEK_API_KEY"] = "sk-test-deepseek"
os.environ["KIMI_API_KEY"] = "sk-test-kimi"
os.environ["OPENAI_API_KEY"] = "sk-test-openai"
os.environ["DATABASE_URL"] = "sqlite:///./data/test_tmp.db"
os.environ["FEEDBACK_DB_PATH"] = "./data/test_tmp_feedback.db"
os.environ["SANDBOX_ENABLED"] = "true"


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary data directory with test files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "raw").mkdir(exist_ok=True)
    (data_dir / "processed").mkdir(exist_ok=True)
    yield data_dir


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file for parser tests."""
    csv_path = tmp_path / "test_data.csv"
    csv_path.write_text(
        "time,value,location\n"
        "2024-01-01,1.5,site_a\n"
        "2024-01-02,2.3,site_a\n"
        "2024-01-03,3.1,site_a\n"
        "2024-01-04,2.8,site_a\n"
        "2024-01-05,4.2,site_a\n",
        encoding="utf-8",
    )
    return csv_path


@pytest.fixture
def sample_geojson(tmp_path: Path) -> Path:
    """Create a sample GeoJSON file for parser tests."""
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "site_a", "value": 1.5},
                "geometry": {"type": "Point", "coordinates": [120.1, 30.2]},
            },
            {
                "type": "Feature",
                "properties": {"name": "site_b", "value": 2.3},
                "geometry": {"type": "Point", "coordinates": [120.3, 30.4]},
            },
        ],
    }
    path = tmp_path / "test_data.geojson"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def empty_csv(tmp_path: Path) -> Path:
    """Create an empty CSV file for edge case tests."""
    path = tmp_path / "empty.csv"
    path.write_text("col1,col2\n", encoding="utf-8")
    return path


@pytest.fixture
def feedback_db(tmp_path: Path) -> Path:
    """Create a temporary feedback database with sample feedback records."""
    db_path = tmp_path / "test_feedback.db"

    import sqlite3
    conn = sqlite3.connect(str(db_path))
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

    # Insert sample records
    records = [
        ("msg_1", "session_1", "user_1", 5, "Excellent analysis", '["visualization","color"]', '{"query":"分析GNSS数据","response":"已完成位移时序分析"}'),
        ("msg_2", "session_1", "user_1", 4, "Good, but needs more detail", '["detail"]', '{"query":"检查InSAR形变","response":"形变场分析结果如下"}'),
        ("msg_3", "session_2", "user_1", 1, "Wrong result", '["error"]', '{"query":"降雨量分析","response":"降雨数据为空"}'),
        ("msg_4", "session_1", "user_2", 5, "Perfect", '["accuracy"]', '{"query":"地下水位趋势","response":"水位呈下降趋势"}'),
        ("msg_5", "session_2", "user_2", 3, "OK", '[]', '{}'),
    ]

    for rec in records:
        conn.execute(
            "INSERT INTO feedback (message_id, session_id, user_id, rating, comment, tags, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rec,
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_llm():
    """Create a simple mock LLM for testing."""

    class MockLLM:
        model_id = "mock-llm"

        async def chat(self, messages, temperature=0.7, max_tokens=4096, **kwargs):
            from backend.models.base import ModelResponse
            return ModelResponse(
                content="This is a mock response for testing purposes.",
                model_id="mock-llm",
                token_usage={"total_tokens": 50},
            )

        async def stream_chat(self, messages, temperature=0.7, max_tokens=4096, **kwargs):
            yield "mock token"

    return MockLLM()