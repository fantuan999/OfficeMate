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
