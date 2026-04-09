"""
测试 MySQL 历史消息服务（history_service.py）

前置条件：MySQL 已启动，officemate 数据库和三张表已创建

运行：
    source venv/bin/activate
    python -m pytest tests/test_history_service.py -v
"""
import pytest

from services.history_service import (
    create_session,
    get_or_create_user,
    get_session_messages,
    list_user_sessions,
    save_message,
)

TEST_USERNAME = "_test_user_day10"


@pytest.fixture(autouse=True)
def cleanup_test_user():
    """测试结束后删除测试用户及其数据"""
    yield
    import mysql.connector
    from config import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER
    conn = mysql.connector.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
    )
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE username = %s", (TEST_USERNAME,))
    row = cur.fetchone()
    if row:
        uid = row[0]
        cur.execute("SELECT session_id FROM sessions WHERE user_id = %s", (uid,))
        sids = [r[0] for r in cur.fetchall()]
        for sid in sids:
            cur.execute("DELETE FROM messages WHERE session_id = %s", (sid,))
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (uid,))
    conn.commit()
    cur.close()
    conn.close()


def test_get_or_create_user_creates_new():
    """不存在的用户名应自动创建，默认 employee 角色"""
    user = get_or_create_user(TEST_USERNAME)
    assert user["username"] == TEST_USERNAME
    assert user["role"] == "employee"
    assert "user_id" in user


def test_get_or_create_user_idempotent():
    """相同用户名重复调用应返回同一个用户"""
    u1 = get_or_create_user(TEST_USERNAME)
    u2 = get_or_create_user(TEST_USERNAME)
    assert u1["user_id"] == u2["user_id"]


def test_create_session():
    """应创建 session 并返回合法格式的 session_id"""
    user = get_or_create_user(TEST_USERNAME)
    sid = create_session(user["user_id"])
    assert sid.startswith("officemate_")
    assert len(sid) == len("officemate_") + 8


def test_save_and_get_messages():
    """保存2轮对话后，get_session_messages 应返回正确结构"""
    user = get_or_create_user(TEST_USERNAME)
    sid = create_session(user["user_id"])

    save_message(sid, "user", "年假怎么申请？")
    save_message(sid, "assistant", "需要提前3天在OA提交。")
    save_message(sid, "user", "需要审批吗？")
    save_message(sid, "assistant", "是的，需要直属上级审批。")

    history = get_session_messages(sid)
    assert len(history) == 2
    assert history[0]["question"] == "年假怎么申请？"
    assert history[0]["answer"] == "需要提前3天在OA提交。"
    assert history[1]["question"] == "需要审批吗？"


def test_get_session_messages_respects_limit():
    """get_session_messages 应最多返回 n 轮"""
    user = get_or_create_user(TEST_USERNAME)
    sid = create_session(user["user_id"])

    for i in range(5):
        save_message(sid, "user", f"问题{i}")
        save_message(sid, "assistant", f"答案{i}")

    history = get_session_messages(sid, n=2)
    assert len(history) == 2
    # 应返回最近的2轮（问题3、问题4）
    assert history[-1]["question"] == "问题4"


def test_list_user_sessions():
    """list_user_sessions 应返回有消息的 session，含 preview"""
    user = get_or_create_user(TEST_USERNAME)
    sid = create_session(user["user_id"])
    save_message(sid, "user", "报销需要什么材料？")
    save_message(sid, "assistant", "需要发票和审批单。")

    sessions = list_user_sessions(user["user_id"])
    assert len(sessions) >= 1
    assert sessions[0]["preview"] == "报销需要什么材料？"[:30]
