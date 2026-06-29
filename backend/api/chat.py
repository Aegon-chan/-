"""对话 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/completions")
async def create_chat_completion():
    """创建对话补全"""
    return {"message": "Not implemented yet"}


@router.post("/stream")
async def stream_chat():
    """流式对话"""
    return {"message": "Not implemented yet"}
