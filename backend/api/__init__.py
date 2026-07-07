"""API ????"""

from __future__ import annotations

from fastapi import APIRouter

from .chat import router as chat_router
from .models import router as models_router
from .sessions import router as sessions_router
from .analysis import router as analysis_router
from .knowledge import router as knowledge_router
from .feedback import router as feedback_router
from .self_growth import router as self_growth_router
from .. import uploads
from .database_admin import router as database_admin_router

router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["general"])
router.include_router(models_router, prefix="/models", tags=["general"])
router.include_router(sessions_router, prefix="/sessions", tags=["general"])
router.include_router(analysis_router, prefix="/analysis", tags=["general"])
router.include_router(knowledge_router, prefix="/knowledge", tags=["general"])
router.include_router(feedback_router, prefix="/feedback", tags=["general"])
router.include_router(self_growth_router, prefix="/self-growth", tags=["self_growth"])
router.include_router(uploads.router, prefix="/upload", tags=["general"])
router.include_router(database_admin_router, prefix="/db", tags=["general"])


@router.get("/ping")
async def ping():
    """API ????"""
    return {"ping": "pong"}


