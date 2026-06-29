"""模型管理 API"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_models():
    """列出所有可用模型"""
    from backend.models.registry import ModelRegistry
    return {"models": ModelRegistry.list_models()}


@router.get("/{model_id}")
async def get_model(model_id: str):
    """获取模型详情"""
    from backend.models.registry import ModelRegistry
    model = ModelRegistry.get_model(model_id)
    if model:
        return {"model_id": model.model_id, "status": "active"}
    return {"error": f"Model {model_id} not found"}, 404
