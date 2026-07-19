"""知识库 API 请求/响应模型"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    doc_id: str
    filename: str
    chunk_count: int
    created_at: datetime


class DocumentItem(BaseModel):
    """文档条目"""
    doc_id: str
    filename: str
    chunk_count: int
    created_at: str


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: list[DocumentItem]
    total: int


class SearchRequest(BaseModel):
    """语义检索请求"""
    query: str = Field(..., description="检索查询")
    top_k: int = Field(5, description="返回结果数量", ge=1, le=50)


class SearchResult(BaseModel):
    """检索结果项"""
    content: str
    metadata: dict = Field(default_factory=dict)
    distance: float = 0.0


class SearchResponse(BaseModel):
    """检索响应"""
    query: str
    results: list[SearchResult]
    total: int
