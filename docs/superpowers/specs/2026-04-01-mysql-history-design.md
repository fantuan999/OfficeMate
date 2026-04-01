---
name: MySQL User Auth & History
description: Phase 2 Day 7 — username-based auth with roles, MySQL-persisted conversation history
type: project
---

# MySQL User Auth & Conversation History — Design Spec

## Overview

Replace the current JSON-file session storage with MySQL-backed user authentication and conversation history. Users identify themselves by username (no password for now). Roles distinguish regular employees from admins who can upload documents.

---

## Database Schema

### `users`
| Column | Type | Notes |
|---|---|---|
| user_id | INT AUTO_INCREMENT PK | |
| username | VARCHAR(100) UNIQUE | display name / login key |
| role | ENUM('employee','admin') | default 'employee' |
| created_at | TIMESTAMP | |

### `sessions`
| Column | Type | Notes |
|---|---|---|
| session_id | VARCHAR(50) PK | e.g. `officemate_abc12345` |
| user_id | INT FK → users | |
| created_at | TIMESTAMP | |
| last_updated | TIMESTAMP | updated on each message |

### `messages`
| Column | Type | Notes |
|---|---|---|
| id | INT AUTO_INCREMENT PK | |
| session_id | VARCHAR(50) FK → sessions | |
| role | ENUM('user','assistant') | |
| content | TEXT | |
| created_at | TIMESTAMP | |

---

## `history_service.py` — Public API

```python
get_or_create_user(username: str) -> dict
# Returns: {"user_id": int, "username": str, "role": str}
# Creates user with role="employee" if not exists

create_session(user_id: int) -> str
# Returns: new session_id (e.g. "officemate_abc12345")

save_message(session_id: str, role: str, content: str) -> None
# Saves a single message; updates sessions.last_updated

get_session_messages(session_id: str, n: int = MAX_HISTORY_ROUNDS) -> list[dict]
# Returns last n rounds as [{"question": str, "answer": str}, ...]
# Pairs user+assistant messages into turns

list_user_sessions(user_id: int, n: int = 5) -> list[dict]
# Returns: [{"session_id": str, "preview": str, "last_updated": str}, ...]
# Preview = first user message (truncated to 30 chars)
```

---

## Integration Points

### `qa.py` changes
- **Login screen**: on first load (no `session_state.user`), show a username input form. On submit, call `get_or_create_user()` and store result in `session_state.user`.
- **New session**: call `create_session(user_id)` instead of generating UUID locally.
- **Save messages**: after each exchange, call `save_message()` twice (user + assistant).
- **Load history**: call `get_session_messages()` to build history list passed to `ask()`.
- **Sidebar sessions**: replace JSON file scan with `list_user_sessions()`.
- **Role display**: show username in sidebar; admin badge if role == "admin".

### `pages/upload.py` changes
- Top of page: check `session_state.user["role"] == "admin"`. If not, show `st.warning("无上传权限")` and `st.stop()`.

### `qa_service.py` — no changes
- `ask()` still receives `history` as a parameter. `qa.py` is responsible for fetching history from MySQL and passing it in. Keeps qa_service decoupled from the database.

---

## Migration from JSON Sessions

- Existing JSON files in `storage/logs/sessions/` are **not migrated** — they are left in place as legacy data.
- On first load, if no `session_state.user` exists, show login screen (do not auto-load from JSON).
- JSON-based `_save_current_session()`, `_load_session()`, `_list_recent_sessions()` functions in `qa.py` are removed.

---

## Config additions (`config.py`)

```python
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "officemate")
```

(Already present in config.py — no changes needed.)

---

## Error Handling

- If MySQL is unavailable on startup, show `st.error("数据库连接失败，请检查 MySQL 配置")` and `st.stop()`.
- `get_or_create_user()` uses INSERT IGNORE to handle race conditions.
- All DB calls wrapped in try/except; failures surface as Streamlit errors.

---

## Out of Scope

- Password authentication (Phase 2 extension, not now)
- Admin user management UI (create/delete users, change roles)
- Message editing or deletion
