"""对话 API 请求/响应模型"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., description="用户输入的消息")
    model_id: Optional[str] = Field(None, description="模型 ID，留空使用默认模型")


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    message_id: str
    content: str
    model_id: str
    token_usage: dict = Field(default_factory=dict)


class StreamEvent(BaseModel):
    """流式事件"""
    event: str  # token / done / error
    data: str = ""
    session_id: str = ""
    message_id: str = ""
