import json
import time
from datetime import datetime
from uuid import uuid4

import streamlit as st

from config import DOC_CATEGORIES, LOGS_DIR
from services.qa_service import ask

st.set_page_config(
    page_title="OfficeMate",
    page_icon="🏢",
    layout="wide",
)

_WELCOME_MSG = (
    "### 最终回答\n"
    "你好，我是 OfficeMate。你可以直接问我请假、报销、采购、IT 支持和通知总结等问题。\n\n"
    "### 操作步骤/材料清单\n"
    "无\n\n"
    "### 风险提示\n"
    "我的回答以知识库中的制度与流程文档为准。"
)

_RECOMMENDED_QUESTIONS = [
    "年假最晚需要提前几天申请？",
    "报销差旅费需要哪些材料？",
    "采购一台显示器应该怎么走流程？",
    "VPN 连接失败怎么处理？",
]


# ── 工具函数 ───────────────────────────────────────────────
def _new_session():
    """重置为新会话"""
    st.session_state.session_id = f"officemate_{uuid4().hex[:8]}"
    st.session_state.messages = [{"role": "assistant", "content": _WELCOME_MSG, "meta": {}}]
    st.session_state.history = []


def _save_feedback(msg_idx: int, feedback: str):
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
if "session_id" not in st.session_state:
    _new_session()

# pending_question：推荐问题点击后存入，下一轮 rerun 时触发
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── 侧边栏 ─────────────────────────────────────────────────
with st.sidebar:
    st.subheader("对话设置")

    # 知识范围筛选
    category = st.selectbox(
        "知识范围",
        options=DOC_CATEGORIES,
        index=0,
        key="selected_category",
    )

    # 会话 ID
    st.caption("当前会话 ID")
    st.code(st.session_state.session_id, language=None)

    # 新建会话
    if st.button("新建会话", use_container_width=True):
        _new_session()
        st.rerun()

    st.divider()

    # 推荐问题
    st.subheader("推荐问题")
    for q in _RECOMMENDED_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"rec_{q}"):
            st.session_state.pending_question = q
            st.rerun()

# ── 主区域 ─────────────────────────────────────────────────
st.title("🏢 OfficeMate 企业内部文档助手")

# ── 渲染历史消息 ───────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            sources = meta.get("sources", [])
            q_type = meta.get("question_type", "")
            elapsed = meta.get("elapsed", None)

            if sources:
                with st.expander(f"引用来源（{len(sources)} 个文档）"):
                    for src in sources:
                        st.markdown(f"- 📄 `{src}`")

            footer_parts = []
            if q_type:
                footer_parts.append(f"问题类型：{q_type}")
            if elapsed is not None:
                footer_parts.append(f"耗时：{elapsed:.1f}s")
            if footer_parts:
                st.caption(" | ".join(footer_parts))

            col1, col2, col3 = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{i}", help="有帮助"):
                    _save_feedback(i, "helpful")
                    st.toast("感谢反馈！")
            with col2:
                if st.button("👎", key=f"down_{i}", help="需改进"):
                    _save_feedback(i, "needs_improvement")
                    st.toast("已记录，感谢反馈！")


def _process_question(prompt: str):
    """处理一条问题：追加用户消息 → 调用 RAG → 追加助手消息"""
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在检索和生成回答..."):
            t0 = time.time()
            result = ask(
                question=prompt,
                category=None if st.session_state.selected_category == "全部" else st.session_state.selected_category,
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
        "meta": {"sources": sources, "question_type": q_type, "elapsed": elapsed},
    })
    st.session_state.history.append({"question": prompt, "answer": answer})
    _log_qa(prompt, answer, sources, q_type, elapsed)


# ── 处理推荐问题点击 ───────────────────────────────────────
if st.session_state.pending_question:
    pending = st.session_state.pending_question
    st.session_state.pending_question = None
    _process_question(pending)
    st.rerun()

# ── 聊天输入框 ─────────────────────────────────────────────
if prompt := st.chat_input("请输入您的问题，例如：年假怎么申请？"):
    _process_question(prompt)
    st.rerun()
