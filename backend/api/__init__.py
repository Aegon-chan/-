"""API 路由模块"""

from __future__ import annotations

from fastapi import APIRouter

from .chat import router as chat_router
from .models import router as models_router
from .sessions import router as sessions_router
from .analysis import router as analysis_router
from .knowledge import router as knowledge_router

router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["对话"])
router.include_router(models_router, prefix="/models", tags=["模型管理"])
router.include_router(sessions_router, prefix="/sessions", tags=["会话管理"])
router.include_router(analysis_router, prefix="/analysis", tags=["数据分析"])
router.include_router(knowledge_router, prefix="/knowledge", tags=["知识库"])


@router.get("/ping")
async def ping():
    """API 存活检测"""
    return {"ping": "pong"}
