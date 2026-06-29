"""规范条文检索模块"""
from __future__ import annotations

from backend.retrieval.vector_store import get_vector_store


class StandardRetriever:
    """规范条文检索器（查询 collection=standards）"""

    COLLECTION = "standards"

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """检索规范条文"""
        store = get_vector_store()
        return await store.search(query, top_k=top_k, collection_name=self.COLLECTION)

    async def add(self, doc_id: str, content: str, metadata: dict = None) -> None:
        """添加规范条文"""
        store = get_vector_store()
        await store.add_document(
            doc_id, content, metadata=metadata, collection_name=self.COLLECTION
        )
