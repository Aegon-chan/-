"""知识库 API"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/documents")
async def upload_document():
    """上传知识库文档"""
    return {"message": "Not implemented yet"}


@router.get("/documents")
async def list_documents():
    """列出知识库文档"""
    return {"documents": []}


@router.post("/search")
async def search_knowledge():
    """语义检索"""
    return {"message": "Not implemented yet"}
