# OfficeMate — 企业内部文档智能问答系统

> 基于 RAG（Retrieval-Augmented Generation）的企业内部知识库问答系统，
> 集成 Redis 语义缓存层与 Queueing Network 性能评估模块。

---

## 项目定位

**应用层：** 企业员工可上传内部制度、流程、通知文档，通过自然语言提问获取结构化回答。

**研究层：** 研究语义缓存的 eviction 策略在 RAG workload 下的性能表现，结合 Queueing Network 对缓存效率进行定量分析。

---

## 技术栈

| 组件 | 工具 |
|---|---|
| 前端 | Streamlit |
| LLM | 阿里云百炼（DashScope / 通义千问）|
| RAG 编排 | LangChain |
| 向量数据库 | ChromaDB |
| Embeddings | DashScope text-embedding-v4 |
| 语义缓存 | Redis + sentence-transformers |
| 历史消息 | MySQL |
| 混合检索 | BM25（jieba）+ 向量检索 |
| Workload 生成 | NumPy（Zipf）|
| QN 建模 | M/M/1（Phase 3）|

---

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

```env
DASHSCOPE_API_KEY=your_key_here
MYSQL_PASSWORD=your_mysql_password
REDIS_PASSWORD=        # 本地 Redis 无密码留空
```

### 3. 启动依赖服务

```bash
# MySQL（Mac）
sudo /usr/local/mysql/support-files/mysql.server start

# Redis（Mac）
brew services start redis
```

### 4. 初始化 MySQL 数据库

```sql
CREATE DATABASE IF NOT EXISTS officemate;
USE officemate;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    role ENUM('employee', 'admin') DEFAULT 'employee',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器访问 `http://localhost:8501`

---

## 功能说明

### Phase 1 — 基础 RAG 系统

- **文档上传**：支持 PDF / TXT / DOCX / XLSX / CSV，MD5 去重，自动切块并生成向量存入 ChromaDB
- **智能问答**：基于检索到的文档上下文生成结构化回答，包含操作步骤 / 风险提示 / 引用来源
- **知识管理**：查看已上传文档列表、问答日志、用户反馈，支持删除文档

### Phase 2 — 语义缓存 + 存储升级

- **Redis 语义缓存**：对语义相似的问题（cosine similarity > 0.85）直接返回缓存答案，响应时间从 ~6.4s（LLM 生成）降至 ~10ms（缓存命中）。支持四种 eviction 策略：LRU / LFU / TTL / Semantic
- **用户认证与权限**：用户名登录，employee / admin 两种角色。admin 才能上传文档
- **MySQL 历史消息**：对话历史按用户和会话持久化存储，支持跨会话历史恢复
- **混合检索**：BM25（jieba 分词）+ 向量检索，通过 EnsembleRetriever 融合，提升精确词汇的召回率
- **流式输出**：Cache MISS 时逐 token 流式输出；Cache HIT 时逐字打字效果

### Phase 3 — QN 性能评估（进行中）

- Zipf / Poisson / Burst workload 生成器
- 对照实验：Zipf α × similarity threshold × eviction policy
- M/M/1 Queueing Network 建模与可视化

---

## 设置 Admin 用户

默认所有用户为 `employee`，需要手动在 MySQL 中提升权限：

```sql
UPDATE officemate.users SET role='admin' WHERE username='your_username';
```

---

## 运行测试

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

测试覆盖：
- `test_cache_service.py` — Redis 缓存命中 / 未命中 / LRU eviction
- `test_history_service.py` — MySQL 用户创建 / 会话 / 消息存取
- `test_retriever_service.py` — jieba 分词 / BM25 缓存 / 混合检索

---

## 文件结构

```
officemate/
├── app.py                    # Streamlit 主入口
├── config.py                 # 全局配置
├── pages/
│   ├── qa.py                 # 问答对话页
│   ├── upload.py             # 文档上传页（admin）
│   └── manage.py             # 知识管理页
├── services/
│   ├── doc_service.py        # 文档处理（切块、embedding、存储）
│   ├── retriever_service.py  # 混合检索（BM25 + 向量）
│   ├── qa_service.py         # 问答服务（LLM 调用 + 缓存集成）
│   ├── cache_service.py      # Redis 语义缓存
│   └── history_service.py    # MySQL 历史消息
├── tests/                    # 测试文件
├── experiments/              # Phase 3 QN 实验（进行中）
├── docs/superpowers/specs/   # 设计文档
└── storage/                  # ChromaDB / 日志（gitignore）
```
