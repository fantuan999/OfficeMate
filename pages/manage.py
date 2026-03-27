import json
from pathlib import Path

import streamlit as st

from config import LOGS_DIR
from services.doc_service import delete_document, list_documents

st.title("📚 知识管理")
st.caption("查看文档状态、问答记录和用户反馈，便于演示知识库闭环。")

# ── 统计指标 ───────────────────────────────────────────────
docs = list_documents()

qa_logs = []
qa_log_file = LOGS_DIR / "qa_logs.json"
if qa_log_file.exists():
    with open(qa_log_file) as f:
        qa_logs = json.load(f)

feedback_logs = []
feedback_file = LOGS_DIR / "feedback.json"
if feedback_file.exists():
    with open(feedback_file) as f:
        feedback_logs = json.load(f)

covered_categories = len({d["category"] for d in docs}) if docs else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("文档数量", len(docs))
col2.metric("覆盖分类", covered_categories)
col3.metric("问答记录", len(qa_logs))
col4.metric("反馈数量", len(feedback_logs))

st.divider()

# ── 文档列表 ───────────────────────────────────────────────
st.subheader("文档列表")

if not docs:
    st.info("暂无文档，请前往「知识上传」页面上传。")
else:
    upload_log_file = LOGS_DIR / "uploads.json"
    upload_map = {}
    if upload_log_file.exists():
        with open(upload_log_file) as f:
            for log in json.load(f):
                fname = log.get("filename", "")
                if fname:
                    upload_map[fname] = log  # 保留最后一条（最新）

    rows = []
    for doc in docs:
        log = upload_map.get(doc["filename"], {})
        rows.append({
            "title": doc.get("title", Path(doc["filename"]).stem),
            "category": doc["category"],
            "version": doc.get("version", log.get("version", "")),
            "file_name": doc["filename"],
            "chunk_count": log.get("chunk_count", log.get("chunks", "")),
            "uploaded_at": log.get("uploaded_at", log.get("timestamp", "")[:19].replace("T", " ")),
            "status": log.get("status", "success"),
            "source_label": doc.get("source_label", log.get("source_label", "manual")),
        })

    st.dataframe(rows, use_container_width=True)

st.divider()

# ── 删除已上传知识 ─────────────────────────────────────────
st.subheader("删除已上传知识")

if not docs:
    st.info("暂无可删除文档。")
else:
    doc_options = {
        f"{d.get('title', Path(d['filename']).stem)} | {d['category']} | {d.get('version', '')} | {d['filename']}": d["filename"]
        for d in docs
    }
    selected_label = st.selectbox("选择需要删除的文档", options=list(doc_options.keys()))
    selected_filename = doc_options[selected_label]

    st.caption("删除后会同步移除向量索引；历史问答与反馈记录会保留，便于继续演示使用痕迹。")

    confirmed = st.checkbox("我确认删除这份知识文档")

    if st.button("删除选中文档", type="primary", disabled=not confirmed):
        ok = delete_document(selected_filename)
        if ok:
            st.success(f"已删除：{selected_filename}")
            st.rerun()
        else:
            st.error("删除失败，文档可能已不存在。")
