import json
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st

from config import DOC_CATEGORIES, LOGS_DIR
from services.qa_service import ask

# 会话持久化目录
SESSIONS_DIR = LOGS_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

_WELCOME_MSG = "你好，我是 OfficeMate。你可以直接问我请假、报销、采购、IT 支持和通知总结等问题。"

_RECOMMENDED_QUESTIONS = [
    "年假最晚需要提前几天申请？",
    "报销差旅费需要哪些材料？",
    "采购一台显示器应该怎么走流程？",
    "VPN 连接失败怎么处理？",
]


# ── 会话持久化 ─────────────────────────────────────────────
def _save_current_session():
    """将当前会话保存到磁盘（只有有实质内容时才保存）"""
    sid = st.session_state.get("session_id")
    msgs = st.session_state.get("messages", [])
    # 只有用户真正提过问题才保存（消息数 > 1，且包含 user 角色）
    if not sid or not any(m["role"] == "user" for m in msgs):
        return
    session_file = SESSIONS_DIR / f"{sid}.json"
    with open(session_file, "w") as f:
        json.dump({
            "session_id": sid,
            "messages": msgs,
            "history": st.session_state.get("history", []),
            "created_at": st.session_state.get("_session_created", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)


def _load_session(sid: str) -> bool:
    """从磁盘加载指定会话，成功返回 True"""
    session_file = SESSIONS_DIR / f"{sid}.json"
    if not session_file.exists():
        return False
    with open(session_file) as f:
        data = json.load(f)
    st.session_state.session_id = data["session_id"]
    st.session_state.messages = data["messages"]
    st.session_state.history = data.get("history", [])
    st.session_state._session_created = data.get("created_at", "")
    return True


def _list_recent_sessions(n: int = 5) -> list[dict]:
    """列出最近 n 个有内容的会话"""
    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
            # 只列出有用户消息的会话
            if any(m["role"] == "user" for m in data.get("messages", [])):
                # 取第一条用户消息作预览
                first_q = next(
                    (m["content"][:30] for m in data["messages"] if m["role"] == "user"), ""
                )
                sessions.append({
                    "session_id": data["session_id"],
                    "last_updated": data.get("last_updated", ""),
                    "preview": first_q,
                })
        except Exception:
            pass
    sessions.sort(key=lambda x: x["last_updated"], reverse=True)
    return sessions[:n]


def _new_session():
    """保存旧会话 → 新建空会话"""
    _save_current_session()
    sid = f"officemate_{uuid4().hex[:8]}"
    st.session_state.session_id = sid
    st.session_state.messages = [{"role": "assistant", "content": _WELCOME_MSG, "meta": {}}]
    st.session_state.history = []
    st.session_state._session_created = datetime.now().isoformat()


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


# ── 初始化 session state（刷新后自动恢复最近会话）─────────
if "session_id" not in st.session_state:
    recent = _list_recent_sessions(1)
    if recent and _load_session(recent[0]["session_id"]):
        pass  # 成功恢复最近会话
    else:
        _new_session()


# ── CSS：新建会话保留白色边框；推荐/历史按钮去边框左对齐 ──
st.markdown("""
<style>
/* 新建会话 (primary) → 覆盖为白色有边框样式 */
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
    background-color: white !important;
    color: rgb(49, 51, 63) !important;
    border: 1px solid rgba(49, 51, 63, 0.2) !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {
    background-color: rgb(240, 242, 246) !important;
    border-color: rgba(49, 51, 63, 0.4) !important;
}
/* 推荐问题 & 历史会话 (secondary) → 无边框，左对齐文本 */
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: inherit !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 2px 4px !important;
    font-size: 0.9rem !important;
    font-weight: normal !important;
}
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover {
    background: rgba(0, 0, 0, 0.05) !important;
    border-radius: 4px !important;
}
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ─────────────────────────────────────────────────
with st.sidebar:
    st.subheader("对话设置")

    st.selectbox(
        "知识范围",
        options=DOC_CATEGORIES,
        index=0,
        key="selected_category",
    )

    st.caption("当前会话 ID")
    st.code(st.session_state.session_id, language=None)

    # 新建会话：type="primary" + CSS 覆盖成白色有边框
    if st.button("新建会话", type="primary"):
        _new_session()
        st.rerun()

    st.divider()

    # 推荐问题（button 样式，CSS 去掉边框让它像文本链接）
    st.subheader("推荐问题")
    for q in _RECOMMENDED_QUESTIONS:
        if st.button(f"• {q}", key=f"rec_{q}", use_container_width=True):
            # 直接处理，不触发新窗口
            st.session_state._pending_rec_q = q

    st.divider()

    # 历史会话入口
    recent_sessions = _list_recent_sessions(5)
    if recent_sessions:
        st.subheader("历史会话")
        for sess in recent_sessions:
            label = f"{sess['preview'][:20]}…" if sess["preview"] else sess["session_id"]
            is_current = sess["session_id"] == st.session_state.session_id
            btn_label = f"● {label}" if is_current else f"○ {label}"
            if st.button(btn_label, key=f"hist_{sess['session_id']}", use_container_width=True):
                _save_current_session()
                _load_session(sess["session_id"])
                st.rerun()


# ── 主区域 ─────────────────────────────────────────────────
st.title("🏢 OfficeMate 企业内部文档助手")
st.caption("面向企业内部制度、流程、通知与常见 IT 支持问题的轻量级知识助手。")

# ── 渲染历史消息 ───────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            sources = meta.get("sources", [])
            q_type = meta.get("question_type", "")
            elapsed = meta.get("elapsed")

            if sources:
                with st.expander(f"引用来源（{len(sources)} 个文档）"):
                    for src in sources:
                        st.markdown(f"- 📄 `{src}`")

            parts = []
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
    """处理问题，结果渲染到当前脚本执行流中（不触发 rerun）"""
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
    _save_current_session()   # 每次回答后立即持久化


# ── 处理推荐问题点击（同窗口，无 rerun）─────────────────────
if st.session_state.get("_pending_rec_q"):
    q = st.session_state.pop("_pending_rec_q")
    _process_question(q)

# ── 聊天输入框（无 rerun，回答直接渲染在同窗口）──────────
if prompt := st.chat_input("例如：报销差旅费需要提交哪些材料？"):
    _process_question(prompt)
