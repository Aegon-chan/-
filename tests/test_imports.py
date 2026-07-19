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
    assert True
