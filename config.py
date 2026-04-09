import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 路径配置 ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
CHROMA_DIR = STORAGE_DIR / "chroma"
DOCS_DIR = STORAGE_DIR / "docs"
LOGS_DIR = STORAGE_DIR / "logs"

# 确保目录存在
for d in [CHROMA_DIR, DOCS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LLM 配置（阿里云百炼）─────────────────────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_MODEL = "qwen3-max"           # 通义千问 3 max 版本，与 OfficeMate 一致
EMBEDDING_MODEL = "text-embedding-v4"  # DashScope embedding 模型

# ── ChromaDB 配置 ──────────────────────────────────────────
CHROMA_COLLECTION_NAME = "officemate_docs"
CHROMA_PERSIST_DIR = str(CHROMA_DIR)

# ── 文档处理配置 ───────────────────────────────────────────
CHUNK_SIZE = 800        # 每个文本块的字符数（参考 OfficeMate）
CHUNK_OVERLAP = 120     # 相邻块的重叠字符数（保证上下文连贯）
TOP_K_RESULTS = 4       # 检索时返回的最相关文档块数量
BM25_WEIGHT = 0.5       # 混合检索中 BM25 权重
VECTOR_WEIGHT = 0.5     # 混合检索中向量检索权重
MAX_HISTORY_ROUNDS = 4  # 多轮对话保留的历史轮数

# ── 支持的文档格式 ─────────────────────────────────────────
SUPPORTED_FORMATS = [".pdf", ".txt", ".docx", ".xlsx", ".csv"]

# ── 文档分类 ───────────────────────────────────────────────
DOC_CATEGORIES = [
    "全部",
    "HR 政策",
    "财务制度",
    "IT 规范",
    "产品手册",
    "其他",
]

# ── Redis 语义缓存配置（Phase 2）──────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
CACHE_TTL = 3600                   # 缓存过期时间（秒）
CACHE_SIMILARITY_THRESHOLD = 0.85  # cosine 相似度命中阈值
MAX_CACHE_SIZE = 200               # 最大缓存条数，超出触发 eviction
CACHE_EVICTION_POLICY = "lru"      # lru / lfu / ttl / semantic

# ── MySQL 历史消息配置（Phase 2）──────────────────────────
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "officemate")
