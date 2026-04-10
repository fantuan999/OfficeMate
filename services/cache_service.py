import os
import time
from uuid import uuid4
from typing import Optional

import numpy as np
import redis
from sentence_transformers import SentenceTransformer

from config import (
    CACHE_EVICTION_POLICY,
    CACHE_SIMILARITY_THRESHOLD,
    CACHE_TTL,
    MAX_CACHE_SIZE,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

# 模型在模块级别加载一次，避免每次请求重复加载（~500ms）
# 优先用本地缓存路径，避免国内网络访问 HuggingFace 超时
_MODEL_CACHE = os.path.expanduser(
    "~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2"
    "/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
)
_model = SentenceTransformer(_MODEL_CACHE if os.path.exists(_MODEL_CACHE) else "all-MiniLM-L6-v2")

_KEYS_SET = "cache:keys"  # Redis Set，存所有 cache:<uuid> key


def _get_redis() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=False,  # 需要存取 bytes（embedding）
    )


def _encode(text: str) -> np.ndarray:
    """将文本转成 float32 embedding 向量"""
    return _model.encode(text, convert_to_numpy=True).astype(np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度"""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _evict(r: redis.Redis, incoming_embedding: Optional[np.ndarray] = None) -> None:
    """
    根据 CACHE_EVICTION_POLICY 淘汰一条缓存。
    semantic 策略需要传入 incoming_embedding（新问题的向量）。
    """
    keys = [k.decode() for k in r.smembers(_KEYS_SET)]
    if not keys:
        return

    if CACHE_EVICTION_POLICY == "lru":
        # 删除 last_accessed 最旧的
        target = min(keys, key=lambda k: float(r.hget(k, "last_accessed") or 0))

    elif CACHE_EVICTION_POLICY == "lfu":
        # 删除 access_count 最小的
        target = min(keys, key=lambda k: int(r.hget(k, "access_count") or 0))

    elif CACHE_EVICTION_POLICY == "ttl":
        # 删除距离过期最近的（created_at 最早的）
        target = min(keys, key=lambda k: float(r.hget(k, "created_at") or 0))

    elif CACHE_EVICTION_POLICY == "semantic" and incoming_embedding is not None:
        # 删除与新问题余弦相似度最低的（最无关的）
        def similarity_to_incoming(k: str) -> float:
            emb_bytes = r.hget(k, "embedding")
            if emb_bytes is None:
                return 1.0  # 无法比较，保留
            stored = np.frombuffer(emb_bytes, dtype=np.float32)
            return _cosine_similarity(incoming_embedding, stored)
        target = min(keys, key=similarity_to_incoming)

    else:
        # fallback：删最旧的
        target = min(keys, key=lambda k: float(r.hget(k, "created_at") or 0))

    r.delete(target)
    r.srem(_KEYS_SET, target)


def get_cached_answer(question: str) -> Optional[str]:
    """
    查语义缓存。
    - 命中（cosine similarity > threshold）：更新 last_accessed / access_count，返回答案
    - 未命中：返回 None
    """
    r = _get_redis()
    keys = [k.decode() for k in r.smembers(_KEYS_SET)]
    if not keys:
        return None

    query_emb = _encode(question)
    best_key = None
    best_score = -1.0

    for key in keys:
        emb_bytes = r.hget(key, "embedding")
        if emb_bytes is None:
            continue
        stored_emb = np.frombuffer(emb_bytes, dtype=np.float32)
        score = _cosine_similarity(query_emb, stored_emb)
        if score > best_score:
            best_score = score
            best_key = key

    if best_key and best_score >= CACHE_SIMILARITY_THRESHOLD:
        # 更新访问元信息
        r.hset(best_key, mapping={
            "last_accessed": time.time(),
            "access_count": int(r.hget(best_key, "access_count") or 0) + 1,
        })
        answer = r.hget(best_key, "answer")
        return answer.decode("utf-8") if answer else None

    return None


def set_cache(question: str, answer: str) -> None:
    """
    将问题和答案存入 Redis 缓存。
    若缓存已满，先按当前 eviction policy 淘汰一条。
    """
    r = _get_redis()

    # 检查容量，满了先淘汰
    if r.scard(_KEYS_SET) >= MAX_CACHE_SIZE:
        incoming_emb = _encode(question) if CACHE_EVICTION_POLICY == "semantic" else None
        _evict(r, incoming_emb)

    embedding = _encode(question)
    key = f"cache:{uuid4().hex}"
    now = time.time()

    r.hset(key, mapping={ 
        "question": question.encode("utf-8"),
        "answer": answer.encode("utf-8"),
        "embedding": embedding.tobytes(),
        "created_at": now,
        "last_accessed": now,
        "access_count": 1,
    })
    r.expire(key, CACHE_TTL)
    r.sadd(_KEYS_SET, key)


def get_cache_stats() -> dict:
    """返回当前缓存状态，供 UI 和 Phase 3 实验使用"""
    r = _get_redis()
    return {
        "size": r.scard(_KEYS_SET),
        "max_size": MAX_CACHE_SIZE,
        "policy": CACHE_EVICTION_POLICY,
        "threshold": CACHE_SIMILARITY_THRESHOLD,
        "ttl": CACHE_TTL,
    }
