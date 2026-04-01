from uuid import uuid4

import mysql.connector
from mysql.connector import IntegrityError

from config import (
    MAX_HISTORY_ROUNDS,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


def _get_conn():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
    )


def get_or_create_user(username: str) -> dict:
    """
    查找用户，不存在则创建（默认 employee 角色）。
    返回：{"user_id": int, "username": str, "role": str}
    """
    conn = _get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT user_id, username, role FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        if user:
            return user
        # 不存在则插入，用 INSERT IGNORE 防止并发竞争
        cur.execute(
            "INSERT IGNORE INTO users (username, role) VALUES (%s, 'employee')",
            (username,),
        )
        conn.commit()
        cur.execute("SELECT user_id, username, role FROM users WHERE username = %s", (username,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def create_session(user_id: int) -> str:
    """
    为指定用户创建新 session。
    返回：session_id 字符串
    """
    session_id = f"officemate_{uuid4().hex[:8]}"
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sessions (session_id, user_id) VALUES (%s, %s)",
            (session_id, user_id),
        )
        conn.commit()
        return session_id
    finally:
        cur.close()
        conn.close()


def save_message(session_id: str, role: str, content: str) -> None:
    """
    保存一条消息（role = 'user' 或 'assistant'），同时更新 session 的 last_updated。
    """
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content),
        )
        cur.execute(
            "UPDATE sessions SET last_updated = CURRENT_TIMESTAMP WHERE session_id = %s",
            (session_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_session_messages(session_id: str, n: int = MAX_HISTORY_ROUNDS) -> list[dict]:
    """
    取最近 n 轮对话，转成 [{"question": str, "answer": str}, ...] 格式供 qa_service 使用。
    每轮 = 一条 user 消息 + 紧接的一条 assistant 消息。
    """
    conn = _get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        # 取最近 2*n 条消息（n 轮 × 2 条）
        cur.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (session_id, n * 2),
        )
        rows = list(reversed(cur.fetchall()))  # 转回时间正序

        # 将 user/assistant 消息配对成 {question, answer}
        history = []
        i = 0
        while i < len(rows) - 1:
            if rows[i]["role"] == "user" and rows[i + 1]["role"] == "assistant":
                history.append({
                    "question": rows[i]["content"],
                    "answer": rows[i + 1]["content"],
                })
                i += 2
            else:
                i += 1
        return history
    finally:
        cur.close()
        conn.close()


def list_user_sessions(user_id: int, n: int = 5) -> list[dict]:
    """
    列出用户最近 n 个有消息的 session，供侧边栏显示。
    返回：[{"session_id": str, "preview": str, "last_updated": str}, ...]
    """
    conn = _get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT s.session_id, s.last_updated,
                   (SELECT content FROM messages
                    WHERE session_id = s.session_id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) AS preview
            FROM sessions s
            WHERE s.user_id = %s
            ORDER BY s.last_updated DESC
            LIMIT %s
            """,
            (user_id, n),
        )
        rows = cur.fetchall()
        return [
            {
                "session_id": r["session_id"],
                "preview": (r["preview"] or "")[:30],
                "last_updated": str(r["last_updated"]),
            }
            for r in rows
            if r["preview"]  # 只返回有消息的 session
        ]
    finally:
        cur.close()
        conn.close()
