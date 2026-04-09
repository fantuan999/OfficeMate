from typing import Optional

import jieba
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain.retrievers import EnsembleRetriever

from config import (
    BM25_WEIGHT,
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    TOP_K_RESULTS,
    VECTOR_WEIGHT,
)

# ── BM25 模块级缓存 ────────────────────────────────────────
# 避免每次查询都重建索引，只在文档数量变化时重建
_bm25_cache: Optional[BM25Retriever] = None
_bm25_all_docs: list[Document] = []   # 缓存全量文档，供 post-filter 用
_bm25_doc_count: int = 0              # 上次建索引时的文档数


def _get_vectorstore() -> Chroma:
    embeddings = DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )


def _tokenize(text: str) -> list[str]:
    """用 jieba 分词，用于 BM25 索引和查询"""
    return jieba.lcut(text)


def _get_bm25_retriever() -> tuple[BM25Retriever, list[Document]]:
    """
    返回 BM25Retriever 和全量文档列表。
    只有文档数量变化时才重建索引（懒加载）。
    """
    global _bm25_cache, _bm25_all_docs, _bm25_doc_count

    vectorstore = _get_vectorstore()
    results = vectorstore.get()
    current_count = len(results["ids"])

    if _bm25_cache is None or current_count != _bm25_doc_count:
        # 文档数量变化，重建索引
        docs = [
            Document(
                page_content=results["documents"][i],
                metadata=results["metadatas"][i],
            )
            for i in range(current_count)
        ]
        _bm25_all_docs = docs
        _bm25_doc_count = current_count
        _bm25_cache = BM25Retriever.from_documents(
            docs,
            k=TOP_K_RESULTS,
            preprocess_func=_tokenize,
        )

    return _bm25_cache, _bm25_all_docs


def get_retriever(category: Optional[str] = None) -> VectorStoreRetriever:
    """
    纯向量检索器。保留供 Phase 3 对照实验（纯向量 vs 混合）使用。
    """
    vectorstore = _get_vectorstore()
    search_kwargs: dict = {"k": TOP_K_RESULTS}
    if category and category != "全部":
        search_kwargs["filter"] = {"category": category}
    return vectorstore.as_retriever(search_kwargs=search_kwargs)


def get_hybrid_retriever(
    category: Optional[str] = None,
    bm25_weight: float = BM25_WEIGHT,
    vector_weight: float = VECTOR_WEIGHT,
) -> EnsembleRetriever:
    """
    BM25 + 向量混合检索器（EnsembleRetriever）。
    BM25 使用全量文档索引，查询后按 category post-filter。
    向量检索使用 ChromaDB 原生 category filter。
    """
    bm25_retriever, all_docs = _get_bm25_retriever()

    # 如果指定了 category，对 BM25 结果做 post-filter 包装
    if category and category != "全部":
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        from langchain_core.retrievers import BaseRetriever

        class CategoryFilteredBM25(BaseRetriever):
            """BM25Retriever 包装器，过滤指定 category 的结果"""
            _inner: BM25Retriever
            _category: str

            class Config:
                arbitrary_types_allowed = True

            def _get_relevant_documents(
                self, query: str, *, run_manager: CallbackManagerForRetrieverRun
            ) -> list[Document]:
                docs = self._inner.invoke(query)
                return [d for d in docs if d.metadata.get("category") == self._category]

        filtered_bm25 = CategoryFilteredBM25(_inner=bm25_retriever, _category=category)
    else:
        filtered_bm25 = bm25_retriever

    vector_retriever = get_retriever(category)

    return EnsembleRetriever(
        retrievers=[filtered_bm25, vector_retriever],
        weights=[bm25_weight, vector_weight],
    )


def format_docs(docs: list[Document]) -> str:
    """将 Document 列表格式化为 prompt 中的参考材料文本"""
    if not docs:
        return "（知识库中暂无相关文档）"
    return "\n\n---\n\n".join(
        f"【来源：{doc.metadata.get('source_filename', '未知')}】\n{doc.page_content}"
        for doc in docs
    )
