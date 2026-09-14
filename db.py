import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "bot.sqlite3"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                source TEXT NOT NULL,
                service TEXT,
                contact TEXT NOT NULL,
                problem_text TEXT,
                agent_summary TEXT,
                missing_info TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_lead(
    session_id: str,
    source: str,
    service: str | None,
    contact: str,
    problem_text: str | None,
    agent_summary: str | None = None,
    missing_info: str | None = None,
    status: str = "new",
) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO leads
                (session_id, source, service, contact, problem_text, agent_summary, missing_info, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, source, service, contact, problem_text, agent_summary, missing_info, status, created_at),
        )


def save_feedback(session_id: str, message_text: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO feedback (session_id, message_text, created_at) VALUES (?, ?, ?)",
            (session_id, message_text, created_at),
        )
