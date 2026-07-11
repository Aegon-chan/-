"""AI 模型接入模块"""

from __future__ import annotations

import logging

from backend.models.base import BaseLLM, BaseEmbedding, Message, ModelResponse
from backend.models.registry import ModelRegistry
from backend.models.lora_adapter import LoRAAdapterLLM
from backend.models.adapters import DeepSeekAdapter, KimiAdapter
from backend.config import settings

logger = logging.getLogger("research_agent.models")


def init_models() -> None:
    """根据配置初始化并注册所有 AI 模型适配器。

    在应用启动时调用，自动注册：
    - DeepSeek (若 API Key 已配置)
    - KIMI / Moonshot (若 API Key 已配置)
    - OpenAI (若 API Key 已配置)
    """
    registered = 0

    # DeepSeek
    if settings.deepseek_api_key and "your-" not in settings.deepseek_api_key:
        try:
            adapter = DeepSeekAdapter(
                api_key=settings.deepseek_api_key,
                api_base=settings.deepseek_api_base,
            )
            ModelRegistry.register_llm("deepseek-chat", adapter, set_default=True)
            registered += 1
            logger.info("已注册 DeepSeek (deepseek-chat)，设为默认模型")
        except Exception as e:
            logger.warning("DeepSeek 注册失败: %s", e)
    else:
        logger.info("跳过 DeepSeek（未配置 API Key）")

    # KIMI / Moonshot
    if settings.kimi_api_key and "your-" not in settings.kimi_api_key:
        try:
            adapter = KimiAdapter(
                api_key=settings.kimi_api_key,
                api_base=settings.kimi_api_base,
            )
            ModelRegistry.register_llm("moonshot-v1", adapter)
            registered += 1
            logger.info("已注册 KIMI (moonshot-v1)")
        except Exception as e:
            logger.warning("KIMI 注册失败: %s", e)
    else:
        logger.info("跳过 KIMI（未配置 API Key）")

    # OpenAI (备用)
    if settings.openai_api_key and "your-" not in settings.openai_api_key:
        try:
            from backend.models.adapters.openai_compat import OpenAICompatibleLLM
            adapter = OpenAICompatibleLLM(
                model_id="gpt-4o",
                api_key=settings.openai_api_key,
                api_base=settings.openai_api_base,
                model_name="gpt-4o",
            )
            ModelRegistry.register_llm("gpt-4o", adapter)
            registered += 1
            logger.info("已注册 OpenAI (gpt-4o)")
        except Exception as e:
            logger.warning("OpenAI 注册失败: %s", e)
    else:
        logger.info("跳过 OpenAI（未配置 API Key）")

    if registered == 0:
        logger.warning("没有注册任何 AI 模型，请先在 .env 中配置 API Key")
    else:
        logger.info("模型注册完成: %d 个模型可用", registered)


def reload_models() -> None:
    """Reload models from encrypted DB config (with .env fallback).

    Called after API keys are saved/updated via the frontend.
    Clears existing registrations and re-registers from the current config.
    """
    llm_ids = list(ModelRegistry._llms.keys())
    for mid in llm_ids:
        ModelRegistry.remove_llm(mid)

    from backend.api.config import load_decrypted_keys
    db_keys = load_decrypted_keys()

    registered = 0

    deepseek_key = db_keys.get("deepseek") or settings.deepseek_api_key
    if deepseek_key and "your-" not in deepseek_key:
        try:
            adapter = DeepSeekAdapter(
                api_key=deepseek_key,
                api_base=settings.deepseek_api_base,
            )
            ModelRegistry.register_llm("deepseek-chat", adapter, set_default=True)
            registered += 1
            logger.info("Reloaded DeepSeek (deepseek-chat)")
        except Exception as e:
            logger.warning("DeepSeek reload failed: %s", e)
    else:
        logger.info("Skipping DeepSeek (no API key)")

    kimi_key = db_keys.get("kimi") or settings.kimi_api_key
    if kimi_key and "your-" not in kimi_key:
        try:
            adapter = KimiAdapter(
                api_key=kimi_key,
                api_base=settings.kimi_api_base,
            )
            ModelRegistry.register_llm("moonshot-v1", adapter)
            registered += 1
            logger.info("Reloaded KIMI (moonshot-v1)")
        except Exception as e:
            logger.warning("KIMI reload failed: %s", e)
    else:
        logger.info("Skipping KIMI (no API key)")

    openai_key = db_keys.get("openai") or settings.openai_api_key
    if openai_key and "your-" not in openai_key:
        try:
            from backend.models.adapters.openai_compat import OpenAICompatibleLLM
            adapter = OpenAICompatibleLLM(
                model_id="gpt-4o",
                api_key=openai_key,
                api_base=settings.openai_api_base,
                model_name="gpt-4o",
            )
            ModelRegistry.register_llm("gpt-4o", adapter)
            registered += 1
            logger.info("Reloaded OpenAI (gpt-4o)")
        except Exception as e:
            logger.warning("OpenAI reload failed: %s", e)
    else:
        logger.info("Skipping OpenAI (no API key)")

    if registered == 0:
        logger.warning("No AI models registered after reload")
    else:
        logger.info("Model reload complete: %d models available", registered)



__all__ = [
    "BaseLLM", "BaseEmbedding", "Message", "ModelResponse",
    "ModelRegistry",
    "LoRAAdapterLLM",
    "init_models", "reload_models",
]
