"""
向量数据库封装。

基于 ChromaDB 的文档向量化与语义检索服务。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    """向量存储服务"""

    def __init__(self, persist_dir: str = "./data/chroma_db",
                 collection_name: str = "knowledge_base"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_document(self, doc_id: str, content: str,
                           metadata: dict = None) -> None:
        """添加文档到向量库"""
        # 分块处理长文档
        chunks = self._chunk_text(content)
        self.collection.add(
            documents=chunks,
            metadatas=[{"doc_id": doc_id, "chunk": i, **(metadata or {})}
                       for i in range(len(chunks))],
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        )

    async def search(self, query: str, top_k: int = 5,
                     filter: dict = None) -> list[dict]:
        """语义检索"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter,
        )
        docs = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                docs.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        return docs

    async def delete_document(self, doc_id: str) -> None:
        """删除文档"""
        self.collection.delete(where={"doc_id": doc_id})

    def list_documents(self) -> list[str]:
        """列出所有文档 ID"""
        results = self.collection.get()
        doc_ids = set()
        if results["metadatas"]:
            for m in results["metadatas"]:
                if "doc_id" in m:
                    doc_ids.add(m["doc_id"])
        return sorted(doc_ids)

    def count(self) -> int:
        """获取文档块总数"""
        return self.collection.count()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500,
                    overlap: int = 50) -> list[str]:
        """将长文本分块"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks
