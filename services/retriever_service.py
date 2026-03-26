from typing import Optional

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

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


def get_retriever(category: Optional[str] = None) -> VectorStoreRetriever:
    """
    返回向量数据库检索器，可直接用于 LangChain chain。

    用法：
        retriever = get_retriever(category="HR 政策")
        chain = {"context": retriever | format_docs, ...} | prompt | llm | parser
    """
    vectorstore = _get_vectorstore()
    search_kwargs: dict = {"k": TOP_K_RESULTS}
    if category and category != "全部":
        search_kwargs["filter"] = {"category": category}
    return vectorstore.as_retriever(search_kwargs=search_kwargs)


def format_docs(docs: list[Document]) -> str:
    """将 Document 列表格式化为 prompt 中的参考材料文本"""
    if not docs:
        return "（知识库中暂无相关文档）"
    return "\n\n---\n\n".join(
        f"【来源：{doc.metadata.get('source_filename', '未知')}】\n{doc.page_content}"
        for doc in docs
    )
