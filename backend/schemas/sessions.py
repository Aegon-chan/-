"""会话管理 API 请求/响应模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: str = Field("新会话", description="会话标题")
    model_id: str = Field("deepseek-chat", description="使用的模型 ID")
    system_prompt: str = Field("", description="系统提示词")


class SessionUpdate(BaseModel):
    """更新会话请求"""
    title: Optional[str] = None
    model_id: Optional[str] = None


class SessionResponse(BaseModel):
    """会话概要"""
    id: str
    title: str
    model_id: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(BaseModel):
    """会话详情（含消息列表）"""
    id: str
    title: str
    model_id: str
    system_prompt: str = ""
    messages: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """会话列表"""
    sessions: list[SessionResponse]
    total: int
