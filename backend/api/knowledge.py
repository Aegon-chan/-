"""知识库 API 路由"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, UploadFile, File

from backend.retrieval.vector_store import get_vector_store, VectorStore
from backend.schemas.knowledge import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentItem,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from backend.core.exceptions import ValidationError

router = APIRouter()


@router.post("/documents", response_model=DocumentUploadResponse, summary="上传文档")
async def upload_document(
    file: UploadFile = File(..., description="文档文件 (PDF/TXT/MD)"),
):
    """上传知识库文档，自动提取文本并向量化存储"""
    # 校验文件类型
    allowed_ext = {".txt", ".md", ".pdf"}
    filename = file.filename or "unknown.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed_ext:
        raise ValidationError(
            message=f"不支持的文件格式: {ext}",
            detail=f"支持: {', '.join(allowed_ext)}",
        )

    # 读取字节流
    raw = await file.read()

    # 提取文本（PDF 用 pdfplumber，其他用 UTF-8）
    content = VectorStore.extract_text_from_bytes(raw, filename=filename)
    if not content.strip():
        raise ValidationError(message="文件内容为空或无法提取文字")

    # 生成 doc_id
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    doc_id = f"doc_{ts}_{filename}"

    # 向量化存储
    store = get_vector_store()
    await asyncio.to_thread(store.add_document, 
        doc_id=doc_id,
        content=content,
        metadata={"filename": filename, "ext": ext},
    )

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=filename,
        chunk_count=len(content) // 500 + 1,
        created_at=datetime.utcnow(),
    )


@router.get("/documents", response_model=DocumentListResponse, summary="文档列表")
async def list_documents():
    """列出知识库中的所有文档"""
    store = get_vector_store()
    doc_ids = store.list_documents()
    items = []
    for did in doc_ids:
        items.append(
            DocumentItem(
                doc_id=did,
                filename=did.split("_", 2)[-1] if "_" in did else did,
                chunk_count=0,
                created_at=did.split("_")[1] if len(did.split("_")) > 1 else "",
            )
        )
    return DocumentListResponse(documents=items, total=len(items))


@router.delete("/documents/{doc_id}", summary="删除文档")
async def delete_document(doc_id: str):
    """从知识库删除文档"""
    store = get_vector_store()
    await store.delete_document(doc_id)
    return {"deleted": doc_id, "ok": True}


@router.post("/search", response_model=SearchResponse, summary="语义检索")
async def search_knowledge(body: SearchRequest):
    """对知识库进行语义检索"""
    store = get_vector_store()
    results = await asyncio.to_thread(store.search, query=body.query, top_k=body.top_k)
    return SearchResponse(
        query=body.query,
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )
