"""Research Agent — 基本测试"""
from __future__ import annotations

from backend.config import settings


def test_config_loaded():
    assert settings.app_name == "ResearchAgent"
    assert settings.app_env in ("development", "staging", "production")


def test_data_dirs_exist():
    assert settings.data_dir.exists()
    assert settings.data_dir.is_dir()


def test_imports():
    from backend.db.session import Base, get_async_session
    from backend.models.base import BaseLLM, ModelResponse
    from backend.models.registry import ModelRegistry
    from backend.core.agent import ResearchAgent
    from backend.core.memory import MemoryStore
    from backend.core.sandbox import CodeSandbox
    from backend.retrieval.vector_store import VectorStore
    from backend.reporting.report_generator import ReportGenerator
    assert True
