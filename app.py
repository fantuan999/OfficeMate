import json
import time
from datetime import datetime

import streamlit as st

from config import DOC_CATEGORIES, LOGS_DIR
from services.qa_service import ask

st.set_page_config(
    page_title="OfficeMate",
    page_icon="🏢",
    layout="wide",
)


# ── 工具函数（必须在调用前定义）──────────────────────────
def _save_feedback(msg_idx: int, feedback: str):
    """将用户反馈写入日志"""
    log_file = LOGS_DIR / "feedback.json"
    logs = []
    if log_file.exists():
        with open(log_file) as f:
            logs = json.load(f)
    if msg_idx < len(st.session_state.messages):
        msg = st.session_state.messages[msg_idx]
        logs.append({
            "feedback": feedback,
            "answer_preview": msg["content"][:100],
            "timestamp": datetime.now().isoformat(),
        })
    with open(log_file, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def _log_qa(question: str, answer: str, sources: list, q_type: str, elapsed: float):
    """将问答记录写入 qa_logs.json"""
    log_file = LOGS_DIR / "qa_logs.json"
    logs = []
    if log_file.exists():
        with open(log_file) as f:
            logs = json.load(f)
    logs.append({
        "question": question,
        "answer_preview": answer[:200],
        "sources": sources,
        "question_type": q_type,
        "response_time_s": round(elapsed, 2),
        "timestamp": datetime.now().isoformat(),
    })
    with open(log_file, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# ── 初始化 session state ───────────────────────────────────
if "messages" not in st.session_state:
    # 每条消息：{"role": "user"/"assistant", "content": str, "meta": dict}
    st.session_state.messages = []
if "history" not in st.session_state:
    # 传给 qa_service 的格式：[{"question": str, "answer": str}]
    st.session_state.history = []

# ── 侧边栏 ─────────────────────────────────────────────────
with st.sidebar:
    st.title("🏢 OfficeMate")
    st.caption("企业内部文档智能助手")
    st.divider()

    category = st.selectbox(
        "检索范围",
        options=DOC_CATEGORIES,
        index=0,
        help="选择要检索的文档分类，默认检索全部",
    )

    st.divider()
    st.page_link("pages/upload.py", label="上传文档", icon="📤")
    st.page_link("pages/manage.py", label="知识管理", icon="📚")

    st.divider()
    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()

# ── 主页面标题 ─────────────────────────────────────────────
st.title("企业内部文档问答")
st.caption(f"当前检索范围：{'全部文档' if category == '全部' else category}")

# ── 欢迎提示（无消息时显示）───────────────────────────────
if not st.session_state.messages:
    st.info("请先在「上传文档」页面上传企业文档，然后在此提问。")

# ── 渲染历史消息 ───────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            meta = msg.get("meta", {})
            sources = meta.get("sources", [])
            q_type = meta.get("question_type", "")

            if sources:
                with st.expander(f"引用来源（{len(sources)} 个文档）"):
                    for src in sources:
                        st.markdown(f"- 📄 `{src}`")

            col1, col2, col3 = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{i}", help="有帮助"):
                    _save_feedback(i, "helpful")
                    st.toast("感谢反馈！")
            with col2:
                if st.button("👎", key=f"down_{i}", help="需改进"):
                    _save_feedback(i, "needs_improvement")
                    st.toast("已记录，感谢反馈！")

# ── 聊天输入 ───────────────────────────────────────────────
if prompt := st.chat_input("请输入您的问题，例如：年假怎么申请？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在检索和生成回答..."):
            t0 = time.time()
            result = ask(
                question=prompt,
                category=None if category == "全部" else category,
                history=st.session_state.history,
            )
            elapsed = time.time() - t0

        answer = result["answer"]
        sources = result["sources"]
        q_type = result["question_type"]

        st.markdown(answer)

        if sources:
            with st.expander(f"引用来源（{len(sources)} 个文档）"):
                for src in sources:
                    st.markdown(f"- 📄 `{src}`")

        st.caption(f"问题类型：{q_type} | 耗时：{elapsed:.1f}s")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "meta": {"sources": sources, "question_type": q_type},
    })
    st.session_state.history.append({"question": prompt, "answer": answer})
    _log_qa(prompt, answer, sources, q_type, elapsed)
    st.rerun()
