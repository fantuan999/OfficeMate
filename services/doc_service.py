import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredExcelLoader,
)
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    DASHSCOPE_API_KEY,
    DOCS_DIR,
    EMBEDDING_MODEL,
    LOGS_DIR,
    STORAGE_DIR,
    SUPPORTED_FORMATS,
)

MD5_INDEX_FILE = STORAGE_DIR / "md5_index.json"


def _compute_md5(file_path: Path) -> str:
    """计算文件内容的 MD5 哈希值"""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _load_md5_index() -> dict:
    """读取 MD5 索引文件，返回 {filename: md5} 字典"""
    if not MD5_INDEX_FILE.exists():
        return {}
    with open(MD5_INDEX_FILE) as f:
        return json.load(f)


def _save_md5_index(index: dict):
    """保存 MD5 索引到文件"""
    with open(MD5_INDEX_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def is_duplicate(file_path: Path) -> Optional[str]:
    """
    检查文件是否已存在（通过 MD5 对比内容，而非文件名）
    返回：已存在的文件名（若重复），或 None（若是新文件）
    """
    new_md5 = _compute_md5(file_path)
    index = _load_md5_index()
    for filename, md5 in index.items():
        if md5 == new_md5:
            return filename  # 返回原来的文件名，方便提示用户
    return None


def _get_embeddings():
    """初始化 DashScope Embedding 模型"""
    return DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )


def _get_vectorstore():
    """获取 ChromaDB 向量数据库实例"""
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


def _load_document(file_path: Path):
    """根据文件格式选择对应的 Loader 加载文档"""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        loader = PyPDFLoader(str(file_path))
    elif suffix == ".txt":
        loader = TextLoader(str(file_path), encoding="utf-8")
    elif suffix == ".docx":
        loader = Docx2txtLoader(str(file_path))
    elif suffix == ".xlsx":
        loader = UnstructuredExcelLoader(str(file_path))
    elif suffix == ".csv":
        loader = CSVLoader(str(file_path), encoding="utf-8")
    else:
        raise ValueError(f"不支持的文件格式：{suffix}")
    return loader.load()


def process_and_store(file_path: Path, category: str, filename: str) -> dict:
    """
    完整的文档处理流程：MD5去重 → 加载 → 切块 → embedding → 存入 ChromaDB

    返回：{"chunks": int, "filename": str, "category": str}
    """
    # 0. MD5 去重检查（比对内容，与文件名无关）
    existing = is_duplicate(file_path)
    if existing:
        raise ValueError(f"文档内容与已上传的「{existing}」重复，跳过导入")

    # 1. 加载文档
    docs = _load_document(file_path)

    # 2. 切块
    # RecursiveCharacterTextSplitter 会按段落、句子、词依次切割，保证语义完整性
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)

    # 3. 给每个块加上 metadata（分类、来源文件名）
    for chunk in chunks:
        chunk.metadata["category"] = category
        chunk.metadata["source_filename"] = filename

    # 4. 存入 ChromaDB（内部自动调用 DashScope API 生成 embedding）
    vectorstore = _get_vectorstore()
    vectorstore.add_documents(chunks)

    # 5. 记录 MD5 索引
    index = _load_md5_index()
    index[filename] = _compute_md5(file_path)
    _save_md5_index(index)

    # 6. 记录日志
    _log_upload(filename, category, len(chunks))

    return {"chunks": len(chunks), "filename": filename, "category": category}


def delete_document(filename: str) -> bool:
    """从 ChromaDB 和 MD5 索引中删除指定文件名的所有记录"""
    vectorstore = _get_vectorstore()
    results = vectorstore.get(where={"source_filename": filename})
    if not results["ids"]:
        return False
    vectorstore.delete(ids=results["ids"])

    # 同步清除 MD5 索引
    index = _load_md5_index()
    index.pop(filename, None)
    _save_md5_index(index)

    return True


def list_documents() -> list[dict]:
    """列出所有已上传文档（去重，按文件名聚合）"""
    vectorstore = _get_vectorstore()
    results = vectorstore.get()
    if not results["metadatas"]:
        return []

    seen = {}
    for meta in results["metadatas"]:
        fname = meta.get("source_filename", "未知")
        if fname not in seen:
            seen[fname] = {
                "filename": fname,
                "category": meta.get("category", "其他"),
            }
    return list(seen.values())


def save_uploaded_file(uploaded_file) -> Path:
    """将 Streamlit 上传的文件保存到本地 storage/docs/"""
    dest = DOCS_DIR / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def _log_upload(filename: str, category: str, chunks: int):
    """记录上传日志到 storage/logs/"""
    log_file = LOGS_DIR / "uploads.json"
    logs = []
    if log_file.exists():
        with open(log_file) as f:
            logs = json.load(f)
    logs.append({
        "filename": filename,
        "category": category,
        "chunks": chunks,
        "timestamp": datetime.now().isoformat(),
    })
    with open(log_file, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
