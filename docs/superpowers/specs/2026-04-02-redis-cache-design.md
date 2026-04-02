---
name: Redis Semantic Cache
description: Phase 2 Day 6 — Redis KV semantic cache with 4 eviction policies, bounded by MAX_CACHE_SIZE
type: project
---

# Redis Semantic Cache — Design Spec

## Overview

Add a semantic cache layer between the user query and the RAG pipeline. When a new question is semantically similar (cosine similarity > threshold) to a previously cached question, return the cached answer directly without calling ChromaDB or the LLM. This is the core research contribution for Task 4.3.

---

## Redis Data Model

Each cache entry is stored as a Redis Hash with key `cache:<uuid>`:

| Field | Type | Description |
|---|---|---|
| question | str | Original question text |
| answer | str | LLM answer |
| embedding | bytes | numpy float32 array serialized with tobytes() |
| created_at | float | Unix timestamp |
| last_accessed | float | Unix timestamp, updated on HIT (LRU) |
| access_count | int | Incremented on HIT (LFU) |

A Redis Set `cache:keys` tracks all active cache keys for O(1) enumeration.

---

## `cache_service.py` — Public API

```python
get_cached_answer(question: str) -> Optional[str]
# 1. Encode question with sentence-transformers
# 2. Fetch all cache entries from Redis
# 3. Compute cosine similarity against each stored embedding
# 4. If best match > CACHE_SIMILARITY_THRESHOLD: update last_accessed/access_count, return answer
# 5. Otherwise: return None

set_cache(question: str, answer: str) -> None
# 1. Check current cache size against MAX_CACHE_SIZE
# 2. If full: call _evict() to remove one entry based on CACHE_EVICTION_POLICY
# 3. Encode question with sentence-transformers
# 4. Store Redis Hash with TTL = CACHE_TTL
# 5. Add key to cache:keys set

get_cache_stats() -> dict
# Returns: {"size": int, "max_size": int, "policy": str, "threshold": float}
# Used by UI and Phase 3 experiments
```

---

## Eviction Policies

Controlled by `CACHE_EVICTION_POLICY` in config. Called when `len(cache:keys) >= MAX_CACHE_SIZE`:

| Policy | Logic |
|---|---|
| `lru` | Delete entry with smallest `last_accessed` |
| `lfu` | Delete entry with smallest `access_count` |
| `ttl` | No active eviction — rely on Redis TTL expiry. If cache is full, delete the entry closest to expiry (smallest `created_at + CACHE_TTL - now`) |
| `semantic` | Delete entry with lowest cosine similarity to the *incoming* new question — keeps the most relevant entries |

---

## Config Additions (`config.py`)

```python
MAX_CACHE_SIZE = 200          # max entries before eviction triggers
CACHE_EVICTION_POLICY = "lru" # lru / lfu / ttl / semantic
# CACHE_TTL and CACHE_SIMILARITY_THRESHOLD already present
```

---

## Integration: `qa_service.py`

Refactor `ask()` with two changes:

**1. Retriever moved out of chain (discussed earlier):**
```python
docs = retriever.invoke(question)
context = format_docs(docs)
sources = [...]
```

**2. Cache wrap around full pipeline:**
```python
cached = get_cached_answer(question)
if cached:
    return {"answer": cached, "sources": [], "question_type": "...", "cache_hit": True}

# ... RAG pipeline ...

set_cache(question, answer)
return {"answer": answer, "sources": sources, "question_type": q_type, "cache_hit": False}
```

Return dict gains `"cache_hit": bool` field. `qa.py` already reads this field (added in Day 7 work).

---

## Sentence-Transformers Model

Use `all-MiniLM-L6-v2` (already in requirements via sentence-transformers). Fast, 384-dim, good multilingual quality for short queries. Model is loaded once at module level to avoid per-request overhead.

---

## Out of Scope

- Redis password auth (add `REDIS_PASSWORD` to `.env` when needed, already in config)
- Cache invalidation on document deletion
- Distributed / multi-node Redis
