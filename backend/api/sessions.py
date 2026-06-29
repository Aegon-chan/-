"""会话管理 API"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def create_session():
    return {"message": "Not implemented yet"}


@router.get("/")
async def list_sessions():
    return {"sessions": []}


@router.get("/{session_id}")
async def get_session(session_id: str):
    return {"session_id": session_id, "messages": []}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    return {"deleted": session_id}
