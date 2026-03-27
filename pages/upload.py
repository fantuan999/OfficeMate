import json
from pathlib import Path

import streamlit as st

from config import DOC_CATEGORIES, LOGS_DIR, SUPPORTED_FORMATS
from services.doc_service import process_and_store, save_uploaded_file

st.title("📤 知识上传")
st.caption("上传企业内部制度、流程、通知与 FAQ 文档，并补充分类、标题和版本信息。")

# ── 上传表单 ───────────────────────────────────────────────
with st.container(border=True):
    category = st.selectbox(
        "文档分类",
        options=[c for c in DOC_CATEGORIES if c != "全部"],
    )

    version = st.text_input("文档版本", value="v1.0", placeholder="例如：v2026.01")

    uploaded_files = st.file_uploader(
        "上传文档",
        type=["pdf", "txt", "docx", "xlsx", "csv"],
        accept_multiple_files=True,
        label_visibility="visible",
    )

    # 自定义标题仅单文件时可填
    custom_title = ""
    if uploaded_files and len(uploaded_files) == 1:
        custom_title = st.text_input(
            "自定义标题（单文件上传时可选）",
            placeholder="留空则使用文件名作为标题",
        )
    else:
        st.text_input(
            "自定义标题（单文件上传时可选）",
            value="",
            disabled=True,
            placeholder="上传单个文件时可填写",
        )

    if st.button("导入知识库", type="primary", disabled=not uploaded_files):
        ok, dup, fail = 0, 0, 0
        progress = st.progress(0, text="处理中...")
        total = len(uploaded_files)

        for idx, uf in enumerate(uploaded_files):
            progress.progress(idx / total, text=f"正在处理：{uf.name}")
            tmp_path = None
            try:
                tmp_path = save_uploaded_file(uf)
                title = custom_title if (len(uploaded_files) == 1 and custom_title.strip()) else ""
                result = process_and_store(
                    tmp_path, category, uf.name,
                    title=title, version=version, source_label="manual"
                )
                if result is None:
                    st.warning(f"⚠️ {uf.name} 内容重复，已跳过")
                    dup += 1
                else:
                    st.success(f"✅ {result['title']} — {result['chunks']} 块 | {category} | {version}")
                    ok += 1
            except Exception as e:
                st.error(f"❌ {uf.name} 处理失败：{e}")
                fail += 1
            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()

        progress.progress(1.0, text="完成！")
        st.markdown(f"**导入结果：** 成功 {ok} | 重复跳过 {dup} | 失败 {fail}")

st.divider()

# ── 示例知识库 ─────────────────────────────────────────────
st.subheader("示例知识库")
st.caption("如果你暂时没有企业制度文档，可以先导入项目自带的示例文档进行演示。")

sample_dir = Path("sample_docs")
sample_files = list(sample_dir.glob("*")) if sample_dir.exists() else []
supported = [f for f in sample_files if f.suffix.lower() in SUPPORTED_FORMATS]

if st.button("一键导入示例文档"):
    if not supported:
        st.warning("sample_docs/ 目录暂无文件，请先放入 PDF/TXT/DOCX/XLSX/CSV 文件。")
    else:
        ok, dup, fail = 0, 0, 0
        # 示例文档按文件名推断分类（可在此自定义映射）
        _sample_category_map = {
            "hr": "HR 政策", "假": "HR 政策", "假期": "HR 政策",
            "财务": "财务制度", "报销": "财务制度", "差旅": "财务制度",
            "it": "IT 规范", "vpn": "IT 规范", "网络": "IT 规范",
        }
        for f in supported:
            cat = "其他"
            for kw, c in _sample_category_map.items():
                if kw in f.name.lower():
                    cat = c
                    break
            try:
                result = process_and_store(
                    f, cat, f.name,
                    title=f.stem, version="v2026.01", source_label="sample_docs"
                )
                if result is None:
                    dup += 1
                else:
                    ok += 1
            except Exception as e:
                st.error(f"❌ {f.name}：{e}")
                fail += 1
        st.success(f"导入完成：成功 {ok} | 重复跳过 {dup} | 失败 {fail}")

st.divider()

# ── 最近导入文档 ───────────────────────────────────────────
st.subheader("最近导入文档")

log_file = LOGS_DIR / "uploads.json"
if not log_file.exists():
    st.info("暂无上传记录。")
else:
    with open(log_file) as f:
        logs = json.load(f)
    if not logs:
        st.info("暂无上传记录。")
    else:
        rows = [
            {
                "title": log.get("title", ""),
                "category": log.get("category", ""),
                "version": log.get("version", ""),
                "file_type": log.get("file_type", ""),
                "chunk_count": log.get("chunk_count", log.get("chunks", "")),
                "uploaded_at": log.get("uploaded_at", log.get("timestamp", "")[:19].replace("T", " ")),
                "status": log.get("status", "success"),
            }
            for log in reversed(logs[-50:])
        ]
        st.dataframe(rows, use_container_width=True)
