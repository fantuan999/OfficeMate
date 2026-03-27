import json

import streamlit as st

from config import LOGS_DIR
from services.doc_service import delete_document, list_documents

st.set_page_config(page_title="知识管理 - OfficeMate", page_icon="📚", layout="wide")

st.title("📚 知识管理")


# ── 文档列表 ───────────────────────────────────────────────
st.subheader("已上传文档")

docs = list_documents()

if not docs:
    st.info("暂无文档，请前往「上传文档」页面上传。")
else:
    st.caption(f"共 {len(docs)} 个文档")

    for doc in docs:
        col1, col2, col3 = st.columns([5, 2, 1])
        with col1:
            st.markdown(f"📄 `{doc['filename']}`")
        with col2:
            st.caption(doc["category"])
        with col3:
            if st.button("删除", key=f"del_{doc['filename']}", type="secondary"):
                ok = delete_document(doc["filename"])
                if ok:
                    st.success(f"已删除：{doc['filename']}")
                    st.rerun()
                else:
                    st.error("删除失败")

st.divider()

# ── 问答日志 ───────────────────────────────────────────────
st.subheader("问答日志")

qa_log_file = LOGS_DIR / "qa_logs.json"
if not qa_log_file.exists():
    st.info("暂无问答记录。")
else:
    with open(qa_log_file) as f:
        qa_logs = json.load(f)

    if not qa_logs:
        st.info("暂无问答记录。")
    else:
        st.caption(f"共 {len(qa_logs)} 条记录")

        # 倒序显示（最新在前）
        for log in reversed(qa_logs[-50:]):
            with st.expander(f"Q: {log['question'][:60]}{'...' if len(log['question']) > 60 else ''}"):
                st.markdown(f"**问题：** {log['question']}")
                st.markdown(f"**回答预览：** {log['answer_preview']}")
                sources = log.get("sources", [])
                if sources:
                    st.markdown(f"**引用来源：** {', '.join(sources)}")
                cols = st.columns(3)
                cols[0].metric("问题类型", log.get("question_type", "-"))
                cols[1].metric("耗时", f"{log.get('response_time_s', 0):.1f}s")
                cols[2].caption(log.get("timestamp", ""))

st.divider()

# ── 上传日志 ───────────────────────────────────────────────
st.subheader("上传日志")

upload_log_file = LOGS_DIR / "uploads.json"
if not upload_log_file.exists():
    st.info("暂无上传记录。")
else:
    with open(upload_log_file) as f:
        upload_logs = json.load(f)

    if not upload_logs:
        st.info("暂无上传记录。")
    else:
        st.caption(f"共 {len(upload_logs)} 次上传")
        rows = [
            {
                "文件名": log["filename"],
                "分类": log["category"],
                "切块数": log["chunks"],
                "时间": log["timestamp"][:19].replace("T", " "),
            }
            for log in reversed(upload_logs[-100:])
        ]
        st.dataframe(rows, use_container_width=True)
