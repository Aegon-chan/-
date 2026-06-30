"""模型管理 API"""
from __future__ import annotations

from fastapi import APIRouter

from backend.models.registry import ModelRegistry
from backend.core.exceptions import NotFoundError

router = APIRouter()


@router.get("/", summary="列出所有可用模型")
async def list_models():
    """列出所有已注册的 LLM 和 Embedding 模型"""
    models = ModelRegistry.list_models()
    return {
        "models": models,
        "total": len(models),
        "default_llm": ModelRegistry._default_llm or "",
    }


@router.get("/{model_id}", summary="获取模型详情")
async def get_model(model_id: str):
    """获取指定模型的详细信息"""
    llm = ModelRegistry.get_llm(model_id)
    if llm:
        return {
            "model_id": llm.model_id,
            "type": "llm",
            "status": "active",
        }

    embedding = ModelRegistry.get_embedding(model_id)
    if embedding:
        return {
            "model_id": embedding.model_id,
            "type": "embedding",
            "status": "active",
        }

    raise NotFoundError(resource="模型", resource_id=model_id)
