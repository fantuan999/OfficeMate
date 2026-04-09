"""
测试 Redis 语义缓存层（cache_service.py）

运行：
    source venv/bin/activate
    python -m pytest tests/test_cache_service.py -v
"""
import pytest
import redis

from config import REDIS_HOST, REDIS_PORT
from services.cache_service import get_cache_stats, get_cached_answer, set_cache

_KEYS_SET = "cache:keys"


@pytest.fixture(autouse=True)
def flush_redis():
    """每个测试前清空 Redis，保证测试互不干扰"""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    r.flushdb()
    yield
    r.flushdb()


def test_set_and_exact_hit():
    """存入后用相同问题查询，应命中"""
    set_cache("年假怎么申请？", "需要提前3天在OA系统提交。")
    result = get_cached_answer("年假怎么申请？")
    assert result is not None
    assert "3天" in result


def test_semantic_hit():
    """语义相近的问题应命中"""
    set_cache("年假怎么申请？", "需要提前3天在OA系统提交。")
    result = get_cached_answer("年假如何申请")
    assert result is not None


def test_unrelated_miss():
    """无关问题不应命中"""
    set_cache("年假怎么申请？", "需要提前3天在OA系统提交。")
    result = get_cached_answer("今天天气怎么样")
    assert result is None


def test_empty_cache_miss():
    """缓存为空时查询应返回 None"""
    result = get_cached_answer("任何问题")
    assert result is None


def test_cache_size_increments():
    """存入多条后 size 应正确增加"""
    set_cache("问题1", "答案1")
    set_cache("问题2", "答案2")
    set_cache("问题3", "答案3")
    stats = get_cache_stats()
    assert stats["size"] == 3


def test_lru_eviction(monkeypatch):
    """缓存满时 LRU 应淘汰最久未访问的条目"""
    monkeypatch.setattr("services.cache_service.MAX_CACHE_SIZE", 3)
    monkeypatch.setattr("services.cache_service.CACHE_EVICTION_POLICY", "lru")

    set_cache("问题A", "答案A")
    set_cache("问题B", "答案B")
    set_cache("问题C", "答案C")

    # 访问 A，使 B 成为最久未访问
    get_cached_answer("问题A")

    # 存第4条，应淘汰 B
    set_cache("问题D", "答案D")

    stats = get_cache_stats()
    assert stats["size"] == 3
    assert get_cached_answer("问题B") is None  # B 被淘汰
    assert get_cached_answer("问题A") is not None
    assert get_cached_answer("问题D") is not None


def test_get_cache_stats_fields():
    """stats 应包含所有必要字段"""
    stats = get_cache_stats()
    assert "size" in stats
    assert "max_size" in stats
    assert "policy" in stats
    assert "threshold" in stats
    assert "ttl" in stats
