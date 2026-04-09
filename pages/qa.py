import time
from datetime import datetime
from pathlib import Path
import json

import streamlit as st

from config import DOC_CATEGORIES, LOGS_DIR
from services.qa_service import ask_stream
from services.history_service import (
    get_or_create_user,
    create_session,
    save_message,
    get_session_messages,
    list_user_sessions,
)

_WELCOME_MSG = "你好，我是 OfficeMate。你可以直接问我请假、报销、采购、IT 支持和通知总结等问题。"

_RECOMMENDED_QUESTIONS = [
    "年假最晚需要提前几天申请？",
    "报销差旅费需要哪些材料？",
    "采购一台显示器应该怎么走流程？",
    "VPN 连接失败怎么处理？",
]


# ── 工具函数 ───────────────────────────────────────────────
def _save_feedback(msg_idx: int, feedback: str):
    log_file = LOGS_DIR / "feedback.json"
    logs = []
    if log_file.exists():
        with open(log_file) as f:
            logs = json.load(f)
    if msg_idx < len(st.session_state.messages):
        logs.append({
            "feedback": feedback,
            "answer_preview": st.session_state.messages[msg_idx]["content"][:100],
            "timestamp": datetime.now().isoformat(),
        })
    with open(log_file, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def _log_qa(question, answer, sources, q_type, elapsed):
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


# ── 登录界面 ───────────────────────────────────────────────
def _show_login():
    st.title("🏢 OfficeMate")
    st.markdown("请输入你的用户名以继续。")
    with st.form("login_form"):
        username = st.text_input("用户名", placeholder="例如：张三 / zhangsan")
        submitted = st.form_submit_button("进入", type="primary")
    if submitted and username.strip():
        try:
            user = get_or_create_user(username.strip())
            st.session_state.user = user
            session_id = create_session(user["user_id"])
            st.session_state.session_id = session_id
            st.session_state.messages = [{"role": "assistant", "content": _WELCOME_MSG, "meta": {}}]
            st.rerun()
        except Exception as e:
            st.error(f"登录失败：{e}")


# ── 如果未登录，显示登录界面 ───────────────────────────────
if "user" not in st.session_state:
    _show_login()
    st.stop()


# ── CSS：推荐问题按钮去除边框 ──────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: inherit !important;
    text-align: left !important;
    padding: 2px 4px !important;
    font-size: 0.9rem !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(0,0,0,0.06) !important;
    border-radius: 4px !important;
}
</style>
""", unsafe_allow_html=True)


# ── 侧边栏 ─────────────────────────────────────────────────
with st.sidebar:
    user = st.session_state.user
    role_badge = " 🔑" if user["role"] == "admin" else ""
    st.markdown(f"**{user['username']}**{role_badge}")
    st.caption(f"会话 ID：{st.session_state.session_id}")

    st.selectbox(
        "知识范围",
        options=DOC_CATEGORIES,
        index=0,
        key="selected_category",
    )

    if st.button("新建会话", use_container_width=True, type="secondary"):
        session_id = create_session(user["user_id"])
        st.session_state.session_id = session_id
        st.session_state.messages = [{"role": "assistant", "content": _WELCOME_MSG, "meta": {}}]
        st.rerun()

    st.divider()

    st.subheader("推荐问题")
    for q in _RECOMMENDED_QUESTIONS:
        if st.button(f"• {q}", key=f"rec_{q}", use_container_width=True):
            st.session_state._pending_rec_q = q

    st.divider()

    recent_sessions = list_user_sessions(user["user_id"], n=5)
    if recent_sessions:
        st.subheader("历史会话")
        for sess in recent_sessions:
            label = f"{sess['preview'][:20]}…" if sess["preview"] else sess["session_id"]
            is_current = sess["session_id"] == st.session_state.session_id
            btn_label = f"● {label}" if is_current else f"○ {label}"
            if st.button(btn_label, key=f"hist_{sess['session_id']}", use_container_width=True):
                st.session_state.session_id = sess["session_id"]
                # 从 MySQL 重建 messages 列表用于渲染
                history = get_session_messages(sess["session_id"], n=50)
                msgs = [{"role": "assistant", "content": _WELCOME_MSG, "meta": {}}]
                for turn in history:
                    msgs.append({"role": "user", "content": turn["question"], "meta": {}})
                    msgs.append({"role": "assistant", "content": turn["answer"], "meta": {}})
                st.session_state.messages = msgs
                st.rerun()

    st.divider()
    if st.button("退出登录", use_container_width=True):
        for key in ["user", "session_id", "messages", "selected_category"]:
            st.session_state.pop(key, None)
        st.rerun()


# ── 主区域 ─────────────────────────────────────────────────
st.title("🏢 OfficeMate 企业内部文档助手")
st.caption("面向企业内部制度、流程、通知与常见 IT 支持问题的轻量级知识助手。")

# ── 渲染历史消息 ───────────────────────────────────────────
for i, msg in enumerate(st.session_state.get("messages", [])):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            sources = meta.get("sources", [])
            q_type = meta.get("question_type", "")
            elapsed = meta.get("elapsed")
            cache_hit = meta.get("cache_hit")

            if sources:
                with st.expander(f"引用来源（{len(sources)} 个文档）"):
                    for src in sources:
                        st.markdown(f"- 📄 `{src}`")

            parts = []
            if cache_hit is not None:
                parts.append("🟢 Cache HIT" if cache_hit else "⚪ Cache MISS")
            if q_type:
                parts.append(f"问题类型：{q_type}")
            if elapsed is not None:
                parts.append(f"耗时：{elapsed:.1f}s")
            if parts:
                st.caption(" | ".join(parts))

            col1, col2, _ = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{i}", help="有帮助"):
                    _save_feedback(i, "helpful")
                    st.toast("感谢反馈！")
            with col2:
                if st.button("👎", key=f"down_{i}", help="需改进"):
                    _save_feedback(i, "needs_improvement")
                    st.toast("已记录，感谢反馈！")


def _process_question(prompt: str):
    st.session_state.messages.append({"role": "user", "content": prompt, "meta": {}})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        t0 = time.time()
        history = get_session_messages(st.session_state.session_id)
        category = None if st.session_state.selected_category == "全部" else st.session_state.selected_category

        # 用 wrapper 捕获 generator 结束后的元数据
        meta_container = {}

        def _stream_with_meta():
            gen = ask_stream(question=prompt, category=category, history=history)
            try:
                while True:
                    yield next(gen)
            except StopIteration as e:
                if e.value:
                    meta_container.update(e.value)

        answer = st.write_stream(_stream_with_meta())
        elapsed = time.time() - t0

        sources = meta_container.get("sources", [])
        q_type = meta_container.get("question_type", "咨询")
        cache_hit = meta_container.get("cache_hit", False)

        if sources:
            with st.expander(f"引用来源（{len(sources)} 个文档）"):
                for src in sources:
                    st.markdown(f"- 📄 `{src}`")

        parts = ["🟢 Cache HIT" if cache_hit else "⚪ Cache MISS", f"问题类型：{q_type}", f"耗时：{elapsed:.1f}s"]
        st.caption(" | ".join(parts))

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "meta": {"sources": sources, "question_type": q_type, "elapsed": elapsed, "cache_hit": cache_hit},
    })

    # 保存到 MySQL
    save_message(st.session_state.session_id, "user", prompt)
    save_message(st.session_state.session_id, "assistant", answer)

    _log_qa(prompt, answer, sources, q_type, elapsed)


# ── 处理推荐问题点击 ───────────────────────────────────────
if st.session_state.get("_pending_rec_q"):
    q = st.session_state.pop("_pending_rec_q")
    _process_question(q)

# ── 聊天输入框 ─────────────────────────────────────────────
if prompt := st.chat_input("例如：报销差旅费需要提交哪些材料？"):
    _process_question(prompt)
