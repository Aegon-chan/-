"""Mobile API adapter - lightweight REST endpoints for mobile clients.

These endpoints wrap the full backend services and return
minimal JSON payloads optimized for mobile consumption.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import json
from pydantic import BaseModel, Field

logger = logging.getLogger("research_agent.mobile")
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────

class MobileChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    session_id: str = Field("default")
    model_id: Optional[str] = None
    user_id: str = Field("default")

class MobileSessionCreate(BaseModel):
    title: str = "New Session"
    model_id: Optional[str] = None
    user_id: str = "default"

class MobileSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = 5

class MobileAnalysisRequest(BaseModel):
    analysis_query: str = Field(..., min_length=1, max_length=2000)
    session_id: str = "default"
    user_id: str = "default"


# ── Helpers ──────────────────────────────────────────────────────────

def _safe_dict(obj) -> dict:
    """Convert any object to a JSON-safe dict."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _safe_dict(v) for k, v in obj.items()}
    return str(obj)


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/health", summary="Mobile health check")
async def mobile_health():
    """Lightweight health check for mobile clients."""
    from backend.db.session import sync_engine
    db_ok = False
    try:
        with sync_engine.connect() as conn:
            conn.execute(sync_engine.text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    from backend.models.registry import ModelRegistry
    try:
        models = ModelRegistry.list_models()
        llm_count = sum(1 for m in models if m["type"] == "llm")
    except Exception:
        llm_count = 0
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "models_available": llm_count,
    }


@router.get("/models", summary="List available models")
async def mobile_models():
    """Return available LLM models (names only, no metadata)."""
    from backend.models.registry import ModelRegistry
    try:
        models = ModelRegistry.list_models()
        return {
            "models": [
                {"id": m["model_id"], "name": m.get("name", m["model_id"])}
                for m in models if m["type"] == "llm"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", summary="Send a chat message")
async def mobile_chat(body: MobileChatRequest):
    """Send a message and get a streaming or non-streaming response."""
    from backend.core.agent import ResearchAgent
    
    try:
        agent = ResearchAgent(
            session_id=body.session_id,
            user_id=body.user_id,
            model_id=body.model_id,
        )
        collected = []
        async for token in agent.stream_chat(body.message):
            collected.append(token)
        response_text = "".join(collected)
        return {"success": True, "response": response_text}
    except Exception as e:
        logger.exception("Mobile chat error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", summary="List sessions")
async def mobile_list_sessions(user_id: str = Query("default")):
    """Return a lightweight session list for mobile."""
    from mobile.api.session_adapter import list_sessions
    try:
        sessions = list_sessions(user_id)
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", summary="Create session")
async def mobile_create_session(body: MobileSessionCreate):
    """Create a new session and return its ID."""
    from mobile.api.session_adapter import create_session
    try:
        session = create_session(user_id=body.user_id, title=body.title, model_id=body.model_id)
        return {"success": True, "session": session}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", summary="Get session messages")
async def mobile_get_session(session_id: str):
    """Return session messages (last 50, lightweight)."""
    from mobile.api.session_adapter import get_session_messages
    try:
        messages = get_session_messages(session_id)
        return {"session_id": session_id, "messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/search", summary="Search knowledge base")
async def mobile_search_knowledge(body: MobileSearchRequest):
    """Search the document knowledge base."""
    from backend.retrieval.vector_store import get_vector_store
    try:
        store = get_vector_store()
        results = await asyncio.to_thread(store.search, body.query, top_k=body.top_k)
        return {
            "query": body.query,
            "results": [
                {
                    "id": r.get("id", ""),
                    "content": r.get("content", "")[:200],
                    "score": r.get("score", 0),
                    "source": r.get("metadata", {}).get("source", ""),
                }
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/execute", summary="Execute NL2Query analysis")
async def mobile_execute_analysis(body: MobileAnalysisRequest):
    """Execute a natural language analysis query."""
    from backend.core.agent import ResearchAgent
    try:
        agent = ResearchAgent(session_id=body.session_id, user_id=body.user_id)
        result = await agent.nl2query_execute(
            query=body.analysis_query,
            data_type="gnss",
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.exception("Mobile analysis error")
        raise HTTPException(status_code=500, detail=str(e))
