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

router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["??"])
router.include_router(models_router, prefix="/models", tags=["????"])
router.include_router(sessions_router, prefix="/sessions", tags=["????"])
router.include_router(analysis_router, prefix="/analysis", tags=["????"])
router.include_router(knowledge_router, prefix="/knowledge", tags=["???"])
router.include_router(feedback_router, prefix="/feedback", tags=["??"])
router.include_router(self_growth_router, prefix="/self-growth", tags=["自成长"])
router.include_router(uploads.router, prefix="/upload", tags=["Upload"])


@router.get("/ping")
async def ping():
    """API ????"""
    return {"ping": "pong"}

