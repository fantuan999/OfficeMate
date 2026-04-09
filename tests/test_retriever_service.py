"""
测试混合检索服务（retriever_service.py）

前置条件：ChromaDB 里至少有一个文档

运行：
    source venv/bin/activate
    python -m pytest tests/test_retriever_service.py -v
"""
import pytest
from langchain_core.documents import Document

from services.retriever_service import (
    _get_bm25_retriever,
    _tokenize,
    format_docs,
    get_hybrid_retriever,
    get_retriever,
)


def test_jieba_tokenize():
    """jieba 分词应正确切分中文"""
    tokens = _tokenize("年假申请流程")
    assert isinstance(tokens, list)
    assert len(tokens) > 0
    assert "申请" in tokens or "年假" in tokens


def test_tokenize_empty():
    """空字符串不应报错"""
    tokens = _tokenize("")
    assert isinstance(tokens, list)


def test_bm25_cache_reuse():
    """第二次调用 _get_bm25_retriever 应返回同一个对象（缓存生效）"""
    r1, _ = _get_bm25_retriever()
    r2, _ = _get_bm25_retriever()
    assert r1 is r2


def test_get_retriever_returns_retriever():
    """get_retriever 应返回可调用的检索器"""
    retriever = get_retriever()
    assert hasattr(retriever, "invoke")


def test_get_hybrid_retriever_returns_retriever():
    """get_hybrid_retriever 应返回可调用的检索器"""
    retriever = get_hybrid_retriever()
    assert hasattr(retriever, "invoke")


def test_hybrid_retriever_invoke():
    """混合检索应能正常调用并返回文档列表"""
    retriever = get_hybrid_retriever()
    docs = retriever.invoke("VPN连接失败")
    assert isinstance(docs, list)


def test_format_docs_empty():
    """空文档列表应返回提示语"""
    result = format_docs([])
    assert "暂无" in result


def test_format_docs_with_content():
    """有文档时应包含来源和内容"""
    docs = [
        Document(
            page_content="VPN重启步骤",
            metadata={"source_filename": "IT手册.pdf"},
        )
    ]
    result = format_docs(docs)
    assert "IT手册.pdf" in result
    assert "VPN重启步骤" in result
