# 待实现的改进点

## 文档去重：MD5 校验

**背景：** 用户可能重复上传同一份文档，导致 ChromaDB 里有重复的 chunk，影响检索质量。

**方案：**
- 上传文件时，先对文件内容计算 MD5 哈希值
- 与已保存的 MD5 记录对比，若命中则拒绝上传并提示"文档已存在"
- MD5 记录现阶段保存到本地文件 `storage/md5_index.json`，格式：
  ```json
  {
    "filename.pdf": "d41d8cd98f00b204e9800998ecf8427e",
    "report.docx": "abc123..."
  }
  ```
- 后续可迁移到 MySQL 或 Redis 存储

**实现位置：** `services/doc_service.py` → `process_and_store()` 函数开头加校验

**伪代码：**
```python
import hashlib

def _compute_md5(file_path: Path) -> str:
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def _is_duplicate(md5: str, filename: str) -> bool:
    # 读取 md5_index.json，检查 md5 是否已存在
    ...
```

**计划实现时间：** 已完成

---

## 文件存储升级：本地临时文件 → 阿里云 OSS

**背景：** 当前上传文件处理完即删除（临时文件方案）。企业场景通常需要保留原始文件用于合规审计和重新处理。

**方案：**
- 用 `oss2` SDK 将原始文件上传到阿里云 OSS
- ChromaDB 的 metadata 里记录 OSS 文件路径
- 支持多实例共享文件，而非依赖本地磁盘

**好处：** 可扩展（多实例）、合规（原始存档）、权限可控

**新增依赖：** `pip install oss2`

**计划实现时间：** Phase 3 之后（可选加分项）

---

## 理论驱动的 Redis TTL 设定（来自 Che 近似）

**背景：** 当前 `cache_service.py` 默认 TTL=3600s，这个值是拍脑袋定的。Che et al. 2002 提供了理论依据：最优 TTL 应约等于缓存的**特征时间 τ**（即缓存满一轮所需时间）。

**方案：**
- 利用 `qn_service.py` 中已有的 `hit_rate_lru(alpha, N, C)` 反推 τ：给定 Zipf α、问题池大小 N、缓存容量 C，解方程 $\sum_{j=1}^{C} (1 - e^{-\lambda_j \tau}) = C$ 得到 τ
- 将 `CACHE_TTL` 设为 `τ * 1.2`（论文建议 ΔT ≈ 1.2τ）
- 在 `config.py` 中暴露为可配置项，支持按实测 α 动态调整

**伪代码：**
```python
from scipy.optimize import brentq
import numpy as np

def compute_optimal_ttl(alpha: float, N: int, C: int, total_lambda: float) -> float:
    """用 Che 近似反推最优 TTL（特征时间 τ）"""
    zipf_probs = np.array([1/i**alpha for i in range(1, N+1)])
    zipf_probs /= zipf_probs.sum()
    lambdas = zipf_probs * total_lambda  # 每个问题的到达率

    def equation(tau):
        return sum(1 - np.exp(-lam * tau) for lam in lambdas) - C

    tau = brentq(equation, 1, 1e7)
    return tau * 1.2  # ΔT = 1.2τ
```

**理论依据：** Che et al. (2002) §IV-B，式 (5)；IMPROVEMENT.md Phase 0 TTL 命中率公式。

**实现位置：** `services/cache_service.py` 初始化时调用，或作为 `qn_service.py` 的工具函数。

**计划实现时间：** Phase 3（QN 评估模块时一并实现）

---

## 一次性问题过滤：频率门槛 + 语义阈值双重过滤

**背景：** 当前 `cache_service.py` 只用 cosine similarity 判断是否命中缓存，但 Che et al. 2002 发现真实流量中 **70%～90% 的请求是一次性请求**——这些请求语义上也可能匹配到缓存，但它们本身几乎不会再出现，缓存它们是浪费。

**方案：**
- 在 `set_cache()` 写入前，检查该问题的历史访问频率
- 只有访问频率高于门槛 $\lambda_{min} = e^{-1}/\tau$（约 0.368/τ）的问题才写入 Redis
- 实现方式：Redis 中维护一个 URL/问题 → 最近两次访问时间戳的轻量表，写入前先查频率

```python
def should_cache(self, question_key: str) -> bool:
    """判断该问题是否值得写入缓存（过滤有效一次性问题）"""
    last_seen = self.redis.get(f"freq:{question_key}")
    if last_seen is None:
        # 第一次见到，记录时间戳但不缓存答案
        self.redis.setex(f"freq:{question_key}", int(self.ttl * 2), time.time())
        return False
    interval = time.time() - float(last_seen)
    lambda_i = 1.0 / interval
    lambda_min = 0.368 / self.tau  # e^-1 / τ
    return lambda_i > lambda_min
```

**好处：** 减少 Redis 内存占用；与 cosine similarity 阈值协同，双重过滤提高缓存精度。

**理论依据：** Che et al. (2002) §III-B 设计原则二；与 IMPROVEMENT.md Phase 0 语义阈值策略互补。

**实现位置：** `services/cache_service.py` → `set_cache()` 方法开头加门槛判断。

**计划实现时间：** Phase 2 Day 6（与语义缓存核心一同实现，或作为优化项）

---

## `hit_rate_lru` 实现：Che 近似公式

**背景：** IMPROVEMENT.md Phase 0 要求实现 `hit_rate_lru(alpha, N, C)`，其数学依据来自 Che et al. 2002 对 LRU 特征时间的推导。

**方案：** 在 Zipf 分布 + IRM（独立参考模型）假设下，LRU 命中率等于特征时间 τ 内被访问到的文档比例，等价于前 C 个最热门问题的概率之和：

$$p_{LRU} = \sum_{i=1}^{C} f_i, \quad f_i = \frac{i^{-\alpha}}{\sum_{j=1}^{N} j^{-\alpha}}$$

```python
import numpy as np

def hit_rate_lru(alpha: float, N: int, C: int) -> float:
    """
    Che 近似：LRU 在 Zipf(alpha, N) 工作负载下，缓存容量 C 时的命中率。
    前提：IRM（独立参考模型），稳态 Zipf 分布。
    来源：Che et al. (2002), IEEE JSAC。
    """
    ranks = np.arange(1, N + 1, dtype=float)
    probs = ranks ** (-alpha)
    probs /= probs.sum()
    return float(probs[:C].sum())
```

**注意：** 这是稳态近似，适用于 Zipf 分布稳定的场景。突发流量（burst）或非稳态下需要用 Phase D 的 Semi-Markov 扩展。

**理论依据：** Che et al. (2002) §II-B，式 (9)(10)；IMPROVEMENT.md Phase 0 第一条。

**实现位置：** `services/qn_service.py`

**计划实现时间：** Phase 3 Day 11

---
