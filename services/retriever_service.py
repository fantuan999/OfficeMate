from typing import Optional

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    TOP_K_RESULTS,
)


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


def retrieve(question: str, category: Optional[str] = None) -> list[dict]:
    """
    根据问题检索最相关的 chunk，返回内容、来源和相似度分数。

    参数：
        question: 用户问题
        category: 文档分类过滤，None 或 "全部" 时不过滤

    返回：[{"content": str, "source": str, "category": str, "score": float}, ...]
    """
    vectorstore = _get_vectorstore()

    filter_dict = None
    if category and category != "全部":
        filter_dict = {"category": category}

    # similarity_search_with_score 同时返回文档和相似度分数
    results = vectorstore.similarity_search_with_score(
        query=question,
        k=TOP_K_RESULTS,
        filter=filter_dict,
    )

    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source_filename", "未知"),
            "category": doc.metadata.get("category", "其他"),
            "score": round(float(score), 4),
        }
        for doc, score in results
    ]
