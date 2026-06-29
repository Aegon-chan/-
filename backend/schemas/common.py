"""通用响应模型"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """统一错误响应"""
    code: str
    message: str
    detail: Any = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    app: str
    env: str


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
