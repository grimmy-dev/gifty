"""SQLite store for runs. One row per contact-run; holds full result + review state."""

import json
import sqlite3
import uuid
from contextlib import contextmanager

from config import settings


@contextmanager
def connect():
    """Yield a SQLite connection, committing on success."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the runs table if absent."""
    with connect() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                status      TEXT NOT NULL,
                data        TEXT NOT NULL,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_run(user_id: str, contact_name: str, data: dict, status: str = "pending_review") -> str:
    run_id = uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute(
            "INSERT INTO runs (id, user_id, contact_name, status, data) VALUES (?,?,?,?,?)",
            (run_id, user_id, contact_name, status, json.dumps(data)),
        )
    return run_id


def get_run(run_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "contact_name": row["contact_name"],
        "status": row["status"],
        "created_at": row["created_at"],
        "data": json.loads(row["data"]),
    }


def update_run(run_id: str, *, status: str | None = None, data: dict | None = None) -> None:
    sets, args = [], []
    if status is not None:
        sets.append("status=?")
        args.append(status)
    if data is not None:
        sets.append("data=?")
        args.append(json.dumps(data))
    if not sets:
        return
    args.append(run_id)
    with connect() as c:
        c.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", args)
