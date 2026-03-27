import os
import tempfile
from pathlib import Path

import streamlit as st

from config import DOC_CATEGORIES, SUPPORTED_FORMATS
from services.doc_service import process_and_store, save_uploaded_file

st.set_page_config(page_title="上传文档 - OfficeMate", page_icon="📤", layout="wide")

st.title("📤 上传文档")
st.caption("支持格式：PDF、TXT、DOCX、XLSX、CSV")

# ── 侧边栏导航 ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏢 OfficeMate")
    st.divider()
    st.page_link("app.py", label="智能问答", icon="💬")
    st.page_link("pages/manage.py", label="知识管理", icon="📚")


# ── 上传区域 ───────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        "选择文件（可多选）",
        type=["pdf", "txt", "docx", "xlsx", "csv"],
        accept_multiple_files=True,
    )

with col2:
    category = st.selectbox(
        "文档分类",
        options=[c for c in DOC_CATEGORIES if c != "全部"],
        help="选择这批文档对应的分类",
    )

if st.button("开始上传", type="primary", disabled=not uploaded_files):
    success_count = 0
    dup_count = 0
    fail_count = 0

    progress = st.progress(0, text="处理中...")
    total = len(uploaded_files)

    for idx, uf in enumerate(uploaded_files):
        progress.progress((idx) / total, text=f"正在处理：{uf.name}")
        tmp_path = None
        try:
            tmp_path = save_uploaded_file(uf)
            result = process_and_store(tmp_path, category, uf.name)
            if result is None:
                st.warning(f"⚠️ {uf.name} 内容重复，已跳过")
                dup_count += 1
            else:
                st.success(f"✅ {uf.name} — 切块 {result['chunks']} 段，分类：{result['category']}")
                success_count += 1
        except Exception as e:
            st.error(f"❌ {uf.name} 处理失败：{e}")
            fail_count += 1
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

    progress.progress(1.0, text="完成！")
    st.divider()
    st.markdown(
        f"**上传结果：** 成功 {success_count} 个 | 重复跳过 {dup_count} 个 | 失败 {fail_count} 个"
    )

st.divider()

# ── 一键导入示例文档 ───────────────────────────────────────
st.subheader("一键导入示例文档")
st.caption("如果 sample_docs/ 目录有文件，点击下方按钮批量导入")

sample_dir = Path("sample_docs")
sample_files = list(sample_dir.glob("*")) if sample_dir.exists() else []
supported = [f for f in sample_files if f.suffix.lower() in SUPPORTED_FORMATS]

if not supported:
    st.info("sample_docs/ 目录暂无示例文档。可将 PDF/TXT/DOCX/XLSX/CSV 文件放入该目录后刷新页面。")
else:
    st.write(f"发现 {len(supported)} 个示例文档：")
    for f in supported:
        st.markdown(f"- `{f.name}`")

    sample_category = st.selectbox(
        "导入分类",
        options=[c for c in DOC_CATEGORIES if c != "全部"],
        key="sample_category",
    )

    if st.button("导入全部示例文档", type="secondary"):
        ok, dup, fail = 0, 0, 0
        for f in supported:
            try:
                result = process_and_store(f, sample_category, f.name)
                if result is None:
                    dup += 1
                else:
                    ok += 1
            except Exception as e:
                st.error(f"❌ {f.name}：{e}")
                fail += 1
        st.success(f"导入完成：成功 {ok} | 重复跳过 {dup} | 失败 {fail}")
