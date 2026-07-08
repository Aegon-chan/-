"""
配置管理模块。

通过 pydantic-settings 从 .env 和环境变量加载所有配置，
支持类型校验、敏感信息脱敏、运行时重载。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 应用 ---
    app_name: str = "ResearchAgent"
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "dev-secret-key-change-in-production"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8010

    # --- 数据库 ---
    database_url: str = "sqlite:///./data/research_agent.db"

    # --- API Keys ---
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    kimi_api_key: str = ""
    kimi_api_base: str = "https://api.moonshot.cn"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"

    # --- 向量数据库 ---
    chroma_persist_dir: str = "./data/chroma_db"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # --- 沙箱 ---
    sandbox_enabled: bool = True
    sandbox_timeout: int = 30
    sandbox_max_memory: int = 512

    # --- 记忆系统 ---
    memory_storage_dir: str = "./data/memories"
    feedback_db_path: str = "./data/feedback.db"
    lora_checkpoint_dir: str = "./data/lora_checkpoints"
    base_model_path: str = "./model_cache/base_model"

    # --- 日志 ---
    log_level: str = "INFO"
    log_file: str = "./data/logs/research_agent.log"

    # --- Feature Flags ---
    feature_self_growth: bool = True
    feature_feedback: bool = True
    feature_finetune: bool = False
    feature_realtime_reports: bool = True

    # --- Monitoring / Metrics ---
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # --- 监测数据库 ---
    monitoring_db_url: str = "sqlite:///./data/monitoring_data.db"
    monitoring_seed_on_startup: bool = True

    @property
    def data_dir(self) -> Path:
        return Path("./data").resolve()

    def ensure_dirs(self) -> None:
        """确保所有数据目录存在。"""
        dirs = [
            self.data_dir,
            Path(self.chroma_persist_dir),
            Path(self.memory_storage_dir),
            Path(self.lora_checkpoint_dir),
            Path(self.base_model_path).parent,
            Path(self.log_file).parent,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
