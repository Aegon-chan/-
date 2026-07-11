"""
模型注册表。

管理所有已注册的 AI 模型适配器，支持运行时动态添加/移除/切换。
"""

from __future__ import annotations

from typing import Optional

from backend.models.base import BaseLLM, BaseEmbedding


class ModelRegistry:
    """全局模型注册表"""

    _llms: dict[str, BaseLLM] = {}
    _embeddings: dict[str, BaseEmbedding] = {}
    _default_llm: str = ""
    _default_embedding: str = ""

    @classmethod
    def register_llm(cls, model_id: str, instance: BaseLLM, set_default: bool = False) -> None:
        """注册 LLM 模型"""
        cls._llms[model_id] = instance
        if set_default or not cls._default_llm:
            cls._default_llm = model_id

    @classmethod
    def register_embedding(cls, model_id: str, instance: BaseEmbedding, set_default: bool = False) -> None:
        """注册嵌入模型"""
        cls._embeddings[model_id] = instance
        if set_default or not cls._default_embedding:
            cls._default_embedding = model_id

    @classmethod
    def get_llm(cls, model_id: Optional[str] = None) -> Optional[BaseLLM]:
        """获取 LLM 实例"""
        model_id = model_id or cls._default_llm
        return cls._llms.get(model_id)

    @classmethod
    def get_llm_with_fallback(cls, model_id: Optional[str] = None) -> Optional[BaseLLM]:
        """获取 LLM，带 fallback 链。

        优先级: 指定模型 → 默认模型 → 任意已注册模型
        """
        # 1. 尝试指定模型
        llm = cls._llms.get(model_id) if model_id else None
        if llm:
            return llm

        # 2. 尝试默认模型
        if model_id != cls._default_llm and cls._default_llm:
            llm = cls._llms.get(cls._default_llm)
            if llm:
                return llm

        # 3. 任意可用模型
        for mid in cls._llms:
            return cls._llms[mid]

        return None

    @classmethod
    def get_embedding(cls, model_id: Optional[str] = None) -> Optional[BaseEmbedding]:
        """获取嵌入模型实例"""
        model_id = model_id or cls._default_embedding
        return cls._embeddings.get(model_id)

    @classmethod
    def list_models(cls) -> list[dict]:
        """列出所有已注册的模型"""
        result = []
        for mid in cls._llms:
            result.append({
                "model_id": mid,
                "type": "llm",
                "default": mid == cls._default_llm,
            })
        for mid in cls._embeddings:
            result.append({
                "model_id": mid,
                "type": "embedding",
                "default": mid == cls._default_embedding,
            })
        return result

    @classmethod
    def remove_llm(cls, model_id: str) -> None:
        """移除 LLM 模型"""
        cls._llms.pop(model_id, None)
        if cls._default_llm == model_id:
            cls._default_llm = next(iter(cls._llms.keys()), "")

    @classmethod
    def remove_embedding(cls, model_id: str) -> None:
        """移除嵌入模型"""
        cls._embeddings.pop(model_id, None)
        if cls._default_embedding == model_id:
            cls._default_embedding = next(iter(cls._embeddings.keys()), "")
