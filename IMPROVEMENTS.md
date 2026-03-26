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

**计划实现时间：** Day 5（整理阶段）

---
