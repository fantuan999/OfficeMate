# OfficeMate with Semantic Cache & QN Eviction

> 基于 [OfficeMate](https://github.com/zhuoly/OfficeMate) 的功能设计，用相同技术栈重新实现，
> 并扩展了 Redis 语义缓存层与 Queueing Network 性能评估模块。

---

## 项目目标

**Research Question:**
> How do semantic similarity thresholds interact with workload skew (Zipf α)
> to affect cache efficiency in RAG systems under Edge constraints?

**双层定位：**
- 应用层：企业内部文档智能问答系统
- 研究层：语义缓存策略评估与 QN 性能分析

---

## 开发原则

1. **先完成基础功能，再逐步加 features**
2. **每完成一步就 git commit + push**
3. **每完成一天的内容，在 Notion 记录修改说明**
4. **每个技术决策都要能解释为什么**

---

## 技术栈

| 组件 | 工具 | 说明 |
|---|---|---|
| 前端 | Streamlit | 快速展示，与 OfficeMate 一致 |
| LLM | 阿里云百炼（DashScope）| 免费额度，与 OfficeMate 一致 |
| RAG 编排 | LangChain | 核心框架 |
| 向量数据库 | ChromaDB | 知识库存储 |
| Embeddings | DashScopeEmbeddings | 语义相似度计算（与 LLM 同一平台）|
| **语义缓存** | **Redis** | **核心贡献（Phase 2）** |
| 历史消息 | MySQL | 多轮对话（Phase 2）|
| 混合检索 | BM25 + 向量 | 检索质量提升（Phase 2）|
| Workload 生成 | NumPy（Zipf）| QN 研究层（Phase 3）|
| 性能可视化 | Matplotlib | 实验结果（Phase 3）|
| QN 建模 | M/M/1 + Random Env | 硕士背景直接用上（Phase 3）|

> **注意：** 语义缓存层的 cosine similarity 计算用 sentence-transformers，因为需要在 Redis 查询时快速计算相似度，不走 API。DashScopeEmbeddings 用于文档索引阶段。

---

## 文件结构

```
officemate-cache/
├── app.py                    # Streamlit 主入口
├── pages/
│   ├── upload.py             # 文档上传页
│   └── manage.py             # 知识管理页
├── services/
│   ├── doc_service.py        # 文档处理（切块、embedding、存储）
│   ├── retriever_service.py  # 检索服务（向量检索 → 混合检索）
│   ├── qa_service.py         # 问答服务（LLM 调用）
│   ├── cache_service.py      # 语义缓存（Phase 2）
│   ├── history_service.py    # 历史消息（Phase 2）
│   └── qn_service.py         # QN 评估（Phase 3）
├── storage/
│   ├── chroma/               # 向量数据库
│   ├── docs/                 # 原始文档
│   └── logs/                 # 问答日志（JSON，Phase 1）
├── experiments/
│   ├── workload_generator.py # Zipf/Poisson/Burst 生成器（Phase 3）
│   ├── run_experiments.py    # 对照实验运行器（Phase 3）
│   └── results/              # 实验结果图表（Phase 3）
├── sample_docs/              # 示例文档
├── config.py                 # 配置项
├── requirements.txt          # 依赖
├── .env.example              # 环境变量模板
├── CLAUDE.md                 # 本文件，开发指南
└── README.md                 # 项目说明
```

---

## 开发阶段规划

### Phase 1 — 基础 RAG 系统（Week 1，Day 1-5）

**目标：能跑的基础版本，功能对标 OfficeMate**

#### Day 1 — 项目初始化 + 环境配置

步骤：
1. 创建项目目录结构
```bash
mkdir -p officemate-cache/{pages,services,storage/{chroma,docs,logs},experiments/results,sample_docs}
touch officemate-cache/{app.py,config.py,requirements.txt,.env.example,README.md}
touch officemate-cache/pages/{upload.py,manage.py}
touch officemate-cache/services/{doc_service.py,retriever_service.py,qa_service.py,cache_service.py,history_service.py,qn_service.py}
touch officemate-cache/experiments/{workload_generator.py,run_experiments.py}
```

2. 创建虚拟环境并安装基础依赖
```bash
cd officemate-cache
python3 -m venv venv
source venv/bin/activate
pip install streamlit langchain langchain-community chromadb sentence-transformers dashscope python-dotenv
# DashScopeEmbeddings 包含在 dashscope 里
# sentence-transformers 用于 Redis 缓存层的快速相似度计算
pip freeze > requirements.txt
```

3. 配置 `.env.example`
```
DASHSCOPE_API_KEY=your_key_here
```

4. 实现 `config.py` — 所有配置项集中管理

5. 初始化 git 并 push
```bash
git init
git add .
git commit -m "Day 1: 项目初始化，目录结构和依赖配置"
git remote add origin https://github.com/你的用户名/officemate-cache.git
git push -u origin main
```

**今天学到的：** 项目工程化结构，虚拟环境，环境变量管理

---

#### Day 2 — 文档处理服务

步骤：
1. 实现 `services/doc_service.py`
   - 支持格式：PDF、TXT、DOCX、XLSX、CSV
   - 文档切块（RecursiveCharacterTextSplitter）
   - Embedding 生成（DashScopeEmbeddings）
   - 存入 ChromaDB

2. 实现 `config.py` 中的 Chroma 配置

3. 写一个简单测试脚本验证文档能被正确切块和存储

4. git push
```bash
git add .
git commit -m "Day 2: 文档处理服务，支持多格式上传和向量存储"
git push
```

**今天学到的：** RAG 索引阶段，文档切块策略，ChromaDB 使用

---

#### Day 3 — 检索服务 + 问答服务

步骤：
1. 实现 `services/retriever_service.py`
   - 向量相似度检索（使用 ChromaDB）
   - 支持按分类过滤（metadata filtering）
   - 返回 top-k 文档和引用来源

2. 实现 `services/qa_service.py`
   - 调用 DashScope API（通义千问）
   - 构建 RAG prompt（包含检索到的文档）
   - 结构化输出：最终回答 / 操作步骤 / 风险提示 / 引用文档

3. 命令行测试：输入问题能得到回答

4. git push
```bash
git add .
git commit -m "Day 3: 检索服务和问答服务，RAG pipeline 基础完成"
git push
```

**今天学到的：** RAG 查询阶段，LangChain chain，DashScope API 调用

---

#### Day 4 — Streamlit 界面

步骤：
1. 实现 `app.py` — 主聊天页
   - 对话式交互
   - 左侧分类过滤
   - 显示引用来源
   - 用户反馈（有帮助/需改进）

2. 实现 `pages/upload.py` — 文档上传页
   - 多格式文件上传
   - 文档分类选择
   - 一键导入示例文档

3. 实现 `pages/manage.py` — 知识管理页
   - 文档列表
   - 问答日志
   - 删除文档功能

4. git push
```bash
git add .
git commit -m "Day 4: Streamlit 多页面界面，对标 OfficeMate 功能"
git push
```

**今天学到的：** Streamlit 多页面，session state，文件上传处理

---

#### Day 5 — 测试 + 修 bug + 整理

步骤：
1. 端到端测试：上传文档 → 提问 → 得到回答 → 查看引用
2. 修复发现的 bug
3. 完善 README.md（项目说明、如何运行）
4. 整理代码，加注释
5. 准备几个示例文档放入 `sample_docs/`

6. git push
```bash
git add .
git commit -m "Day 5: 基础版本完成，bug 修复和文档完善"
git push
```

**Phase 1 完成检查：**
- [ ] 能上传多种格式文档
- [ ] 能按分类检索
- [ ] 能得到结构化回答
- [ ] 能显示引用来源
- [ ] 能查看/删除已上传文档

---

### Phase 2 — 语义缓存 + 存储升级（Week 2，Day 6-10）

**目标：加入 Redis 语义缓存，这是与 OfficeMate 最大的技术差异**

#### Day 6 — Redis 语义缓存层（核心）

步骤：
1. 安装 Redis（本地）和 Python 依赖
```bash
brew install redis  # Mac
pip install redis
```

2. 实现 `services/cache_service.py`
   - `get_cached_answer(question)` — 查缓存
     - 将问题转成 embedding
     - 在 Redis 中找余弦相似度 > threshold 的缓存
     - 返回命中的答案（或 None）
   - `set_cache(question, answer)` — 存缓存
     - 存问题 embedding 和答案
     - 设置 TTL（默认 3600s）
   - 支持 4 种 eviction policy：LRU / LFU / TTL / 语义阈值

3. 在 `qa_service.py` 中集成缓存：
   - 先查缓存 → 命中直接返回 → 未命中走 RAG → 存入缓存

4. 在 UI 中显示 `[Cache HIT]` / `[Cache MISS]` 标签

5. git push
```bash
git add .
git commit -m "Day 6: Redis 语义缓存层，支持 cosine similarity 命中检测"
git push
```

**今天学到的：** Redis 基本操作，cosine similarity 缓存匹配，空间换时间

---

#### Day 7 — MySQL 历史消息

步骤：
1. 安装 MySQL 依赖
```bash
pip install mysql-connector-python sqlalchemy
```

2. 创建数据库和表
```sql
CREATE TABLE qa_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100),
    question TEXT,
    answer TEXT,
    cache_hit BOOLEAN,
    response_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

3. 实现 `services/history_service.py`
   - `save_qa(session_id, question, answer, cache_hit, response_time)`
   - `get_history(session_id)` — 查询历史对话

4. 替换原来的 JSON 日志存储

5. git push
```bash
git add .
git commit -m "Day 7: MySQL 存储历史消息，替换 JSON 文件存储"
git push
```

**今天学到的：** SQLAlchemy ORM，多轮对话存储，结构化日志

---

#### Day 8 — 混合检索（BM25 + 向量）

步骤：
1. 安装依赖
```bash
pip install rank-bm25
```

2. 修改 `services/retriever_service.py`
   - 加入 BM25 关键词检索
   - 用 LangChain `EnsembleRetriever` 融合两种检索
   - 默认权重：0.5 BM25 + 0.5 语义

3. 对比测试：纯向量 vs 混合检索的召回质量

4. git push
```bash
git add .
git commit -m "Day 8: 混合检索（BM25 + 向量），提升精确词匹配能力"
git push
```

**今天学到的：** BM25 原理，混合检索权重调优，EnsembleRetriever

---

#### Day 9 — 流式输出

步骤：
1. 修改 `services/qa_service.py` 支持 streaming
2. 修改 Streamlit UI 用 `st.write_stream()` 展示流式输出
3. 注意：缓存命中时不需要流式（直接返回）

4. git push
```bash
git add .
git commit -m "Day 9: 流式输出，提升用户体验"
git push
```

**今天学到的：** LangChain streaming，Streamlit 实时更新

---

#### Day 10 — 测试 + 整合

步骤：
1. 完整流程测试：上传 → 提问 → 缓存命中 → 历史记录
2. 压力测试：连续提问，观察缓存命中率
3. 修复 bug
4. 更新 README

5. git push
```bash
git add .
git commit -m "Day 10: Phase 2 完成，语义缓存 + MySQL + 混合检索整合测试"
git push
```

**Phase 2 完成检查：**
- [ ] Redis 语义缓存工作正常（命中率 > 50% 重复问题）
- [ ] MySQL 历史消息正确存储
- [ ] 混合检索比纯向量检索召回更准
- [ ] 流式输出正常
- [ ] Cache HIT/MISS 标签在 UI 显示

---

### Phase 3 — QN 性能评估（Week 3，Day 11-14）

**目标：加入 Queueing Network 分析，这是研究层的核心贡献**

#### Day 11 — Workload 生成器

步骤：
1. 实现 `experiments/workload_generator.py`

```python
class WorkloadGenerator:
    def generate_zipf(self, alpha, n_queries, n_unique):
        """Zipf 分布查询 trace"""
        # alpha 控制倾斜程度：α 越大，越少的问题占越多的请求
        
    def generate_poisson(self, rate, duration):
        """Poisson 到达过程"""
        
    def generate_burst(self, normal_rate, burst_rate, burst_duration):
        """突发流量模式"""
```

2. 生成三种 workload trace 并可视化分布

3. git push
```bash
git add .
git commit -m "Day 11: QN workload 生成器，Zipf/Poisson/Burst 三种模式"
git push
```

**今天学到的：** Zipf 分布，泊松过程，M/M/1 队列的到达率建模

---

#### Day 12 — 对照实验设计

步骤：
1. 实现 `experiments/run_experiments.py`

实验矩阵（3 × 3 × 4 = 36 组）：
```
自变量1：Zipf α ∈ {0.5, 1.0, 1.5}
自变量2：Similarity threshold ∈ {0.75, 0.85, 0.95}
缓存策略：LRU / LFU / TTL / 语义阈值

测量指标：
  - Cache hit rate（命中率）
  - P99 latency（延迟）
  - Memory usage（内存占用）
```

2. 跑完所有实验，收集数据到 CSV

3. git push
```bash
git add .
git commit -m "Day 12: 对照实验设计，36 组实验数据收集"
git push
```

**今天学到的：** 控制变量实验设计，M/M/1 服务时间建模，性能指标测量

---

#### Day 13 — 可视化 + Research Insight

步骤：
1. 用 Matplotlib 画三张图：
   - 命中率热力图（α × threshold）
   - P99 延迟对比折线图（4 种 policy）
   - 内存占用对比

2. 写出 research insight（最重要）：

```
目标：能说出类似这样的结论：
"Under high-skew Zipf workloads (α > 1.2),
semantic threshold caching outperforms LRU
by improving hit rate, but a threshold too low
(< 0.8) introduces false positives that
degrade answer quality."
```

3. git push
```bash
git add .
git commit -m "Day 13: 实验可视化和 research insight 分析"
git push
```

---

#### Day 14 — 融会贯通 + GitHub 完善

步骤：
1. 完善 README.md，加入：
   - 系统架构图
   - 实验结果图
   - Research Question 和结论

2. 能不看代码解释整个系统（从上传文档到回答问题）

3. 准备 5 个最可能被面试问到的问题并写出答案：
   - "为什么用 cosine similarity 做缓存命中？"
   - "Zipf α 参数的物理意义是什么？"
   - "为什么 M/M/1 适合这个场景？"
   - "语义阈值策略什么时候会失效？"
   - "你的研究结论能应用到真实 Edge 场景吗？"

4. 最终 push
```bash
git add .
git commit -m "Day 14: 项目完成，README 完善，融会贯通"
git push
```

---

## 面试说法

**应用开发方向：**
> "我做了一个企业文档问答系统，集成 Redis 语义缓存，
> 把重复查询的响应时间从 ~3s 降到 ~50ms，
> 同时用混合检索（BM25 + 向量）提升了检索准确率。"

**PhD / 研究方向：**
> "我用 Queueing Network 对 RAG 查询的 workload 建模，
> 系统研究了 Zipf α 和 cosine similarity threshold
> 如何共同影响缓存效率，发现在高倾斜 workload 下
> 语义阈值策略比 LRU 命中率高约 35%，
> 但阈值过低会引入 false positive，影响答案质量。"

---

## 每天结束后要做的三件事

1. **Git push**（命令在每天步骤里）
2. **在 Notion 记录当天修改**（模板见 Notion 项目页面）
3. **用自己的话解释今天写的每一个函数**（不看代码能说清楚）

---

## 参考资源

- OfficeMate（功能参考）：https://github.com/zhuoly/OfficeMate
- LangChain RAG 教程：https://python.langchain.com/docs/tutorials/rag/
- ChromaDB 文档：https://docs.trychroma.com
- DashScope 文档：https://dashscope.aliyuncs.com
- Redis 文档：https://redis.io/docs
- sentence-transformers：https://www.sbert.net
