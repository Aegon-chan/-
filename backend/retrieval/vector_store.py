"""
向量数据库封装。

基于 ChromaDB + BGE 中文 Embedding 模型的文档向量化与语义检索服务。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings

logger = logging.getLogger("research_agent.retrieval")

# ───────────────────────────── 全局单例 ─────────────────────────────

_vector_store_instance: Optional["VectorStore"] = None


def get_vector_store() -> "VectorStore":
    """获取全局唯一的 VectorStore 实例（惰性初始化）"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance


# ───────────────────────────── 自定义 Embedding 函数 ─────────────────────────


class _BgeEmbeddingFunction:
    """使用 BAAI/bge-small-zh-v1.5 的 Embedding 函数，首次使用自动下载模型"""

    name = "bge_zh"

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self._model_name = model_name
        self._model = None

    def __call__(self, input: list[str]) -> list[list[float]]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self._model_name,
                    cache_folder=str((Path(settings.chroma_persist_dir).parent / "model_cache").resolve()),
                )
                logger.info("Embedding 模型已加载: %s", self._model_name)
            except Exception as e:
                logger.error("Embedding 模型加载失败: %s", e)
                raise RuntimeError(f"Embedding 模型不可用: {e}")

        import numpy as np
        embs = self._model.encode(input, normalize_embeddings=True)
        return embs.tolist() if isinstance(embs, np.ndarray) else embs


# ───────────────────────────── 向量存储 ─────────────────────────────


class VectorStore:
    """向量存储服务"""

    def __init__(self):
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embed_fn: Optional[_BgeEmbeddingFunction] = None
        self._collections: dict[str, chromadb.Collection] = {}

        # 尝试初始化 BGE embedding
        try:
            self._embed_fn = _BgeEmbeddingFunction(model_name=settings.embedding_model)
            self._get_or_create("knowledge_base")
            logger.info("VectorStore 已初始化（BGE embedding）")
        except Exception as e:
            logger.warning("BGE embedding 初始化失败，回退到 ChromaDB 默认: %s", e)
            self._embed_fn = None
            # 后续 _get_or_create 将走 fallback 路径

    def _get_or_create(self, name: str) -> chromadb.Collection:
        """获取或创建 collection（惰性 + 自动 fallback）"""
        if name in self._collections:
            return self._collections[name]

        try:
            if self._embed_fn:
                col = self._client.get_or_create_collection(
                    name=name,
                    embedding_function=self._embed_fn,
                    metadata={"hnsw:space": "cosine"},
                )
            else:
                col = self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
        except Exception:
            # 最终 fallback：不用 embedding 函数
            col = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

        self._collections[name] = col
        return col

    # ── 文档操作 ──────────────────────────────────────────────────

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict = None,
        collection_name: str = "knowledge_base",
    ) -> None:
        """添加文档到向量库"""
        collection = self._get_or_create(collection_name)
        chunks = self._chunk_text(content)
        metadatas = [
            {"doc_id": doc_id, "chunk": i, **(metadata or {})}
            for i in range(len(chunks))
        ]
        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter: dict = None,
        collection_name: str = "knowledge_base",
    ) -> list[dict]:
        """语义检索"""
        collection = self._get_or_create(collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter,
        )
        docs = []
        if results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                docs.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
        return docs

    def delete_document(self, doc_id: str, collection_name: str = "knowledge_base") -> None:
        """删除文档"""
        collection = self._get_or_create(collection_name)
        collection.delete(where={"doc_id": doc_id})

    def list_documents(self, collection_name: str = "knowledge_base") -> list[str]:
        """列出所有文档 ID"""
        collection = self._get_or_create(collection_name)
        results = collection.get()
        doc_ids = set()
        if results.get("metadatas"):
            for m in results["metadatas"]:
                if "doc_id" in m:
                    doc_ids.add(m["doc_id"])
        return sorted(doc_ids)

    def count(self, collection_name: str = "knowledge_base") -> int:
        """获取文档块总数"""
        collection = self._get_or_create(collection_name)
        return collection.count()

    # ── 文件解析 ──────────────────────────────────────────────────

    @staticmethod
    def extract_text_from_bytes(raw: bytes, filename: str = "") -> str:
        """从上传文件提取纯文本（支持 PDF/TXT/MD）"""
        ext = filename.rsplit(".", 1)[-1].lower() if filename else ""

        if ext == "pdf":
            try:
                import io
                import pdfplumber
                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    pages = [p.extract_text() for p in pdf.pages if p.extract_text()]
                return "\n".join(pages)
            except Exception as e:
                logger.warning("PDF 解析失败，回退为原始文本: %s", e)
                return raw.decode("utf-8", errors="replace")

        return raw.decode("utf-8", errors="replace")

    # ── 长文本分块 ──────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
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
