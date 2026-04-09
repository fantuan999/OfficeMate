---
name: Hybrid Retrieval BM25 + Vector
description: Phase 2 Day 8 — EnsembleRetriever combining BM25 (jieba) and vector search
type: project
---

# Hybrid Retrieval (BM25 + Vector) — Design Spec

## Overview

Extend `retriever_service.py` with a hybrid retriever that combines BM25 keyword matching and vector semantic search. The two retrievers run in parallel and are fused via Reciprocal Rank Fusion (RRF) using LangChain's `EnsembleRetriever`. This improves recall for exact keyword queries (e.g. product codes, system names) that semantic search may miss.

---

## Architecture

```
Cache MISS
  ├── BM25Retriever (jieba tokenization)  ──┐
  └── VectorStoreRetriever (DashScope)    ──┴── EnsembleRetriever (RRF) → top-k docs → LLM
```

BM25 and vector retrieval run in parallel. RRF merges their ranked lists: documents ranked highly by both get the highest combined score.

---

## Changes to `retriever_service.py`

**Module-level BM25 cache:**

BM25 index is built once and cached at module level. It is only rebuilt when the document count in ChromaDB changes (i.e. after an upload or deletion). This avoids rebuilding on every query.

```python
_bm25_retriever_cache: Optional[BM25Retriever] = None
_bm25_doc_count: int = 0  # doc count at last build time
```

**New function: `get_hybrid_retriever(category, bm25_weight, vector_weight)`**

Steps:
1. Check current doc count from ChromaDB; rebuild BM25 index only if count changed
2. BM25 index is built from ALL documents (no category filter at index time)
3. Category filtering is applied post-retrieval on BM25 results (filter by `metadata["category"]`)
4. Get `VectorStoreRetriever` with category filter (existing behaviour)
5. Wrap both in `EnsembleRetriever(retrievers=[bm25, vector], weights=[bm25_weight, vector_weight])`

**Why full-corpus BM25 index + post-filter:**
Caching per-category would require N separate indexes. A single full-corpus index is cached once and reused across all category queries; results are filtered after retrieval.

**Existing `get_retriever()` — unchanged.** Kept for backward compatibility and Phase 3 experiments (comparing pure vector vs hybrid).

---

## Changes to `qa_service.py`

Replace `get_retriever()` call with `get_hybrid_retriever()`:

```python
from services.retriever_service import format_docs, get_hybrid_retriever

retriever = get_hybrid_retriever(category)
docs = retriever.invoke(question)
```

---

## Config additions (`config.py`)

```python
BM25_WEIGHT = 0.5    # BM25 contribution weight
VECTOR_WEIGHT = 0.5  # Vector search contribution weight
```

---

## Chinese Tokenization

Use `jieba` for word segmentation:
- `jieba.lcut("年假申请流程")` → `["年假", "申请", "流程"]`
- Applied to both document indexing (at retriever build time) and query tokenization
- BM25Retriever handles query tokenization internally when `preprocess_func=jieba.lcut` is passed

---

## BM25 Category Filtering

ChromaDB's vector retriever supports metadata filtering natively. BM25Retriever does not. Solution: build BM25 index from all documents, then post-filter results by `metadata["category"]` after retrieval. The filtered list is passed to `EnsembleRetriever` as the BM25 results.

---

## Dependencies

```bash
pip install rank-bm25 jieba
```

Both are lightweight and have no transitive conflicts with existing deps.

---

## Out of Scope

- Dynamic BM25 index updates when new documents are uploaded (index is rebuilt per request — acceptable at current scale)
- Weight tuning UI (config values are sufficient for now)
- BM25-only retrieval mode
