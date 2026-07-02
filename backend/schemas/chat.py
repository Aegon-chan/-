"""对话 API 请求/响应模型"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., description="用户输入的消息")
    model_id: Optional[str] = Field(None, description="模型 ID，留空使用默认模型")
    attachments: list[AttachmentSchema] = Field(default_factory=list, description="上传的附件列表")


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    message_id: str
    content: str
    model_id: str
    token_usage: dict = Field(default_factory=dict)



class AttachmentSchema(BaseModel):
    """上传的附件元数据"""
    url: str = Field(..., description="文件访问 URL")
    filename: str = Field(..., description="原始文件名")
    mime_type: str = Field(..., description="MIME 类型")
    size: int = Field(0, description="文件大小（字节）")


class StreamEvent(BaseModel):
    """流式事件"""
    event: str  # token / done / error
    data: str = ""
    session_id: str = ""
    message_id: str = ""
