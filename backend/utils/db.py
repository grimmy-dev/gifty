"""SQLite store for runs. A run is one submission (a batch); each contact in it is
one item row keyed by `run_id`. Per-contact review state lives on the item row."""

import json
import sqlite3
import uuid
from contextlib import contextmanager

from config import settings


@contextmanager
def connect():
    """Yield a SQLite connection, committing on success."""
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL lets readers and the writer proceed concurrently (sync DB calls run in a
    # threadpool); the busy timeout above absorbs brief write contention.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the items table if absent."""
    with connect() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id           TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                status       TEXT NOT NULL,
                data         TEXT NOT NULL,
                created_at   TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_run ON items (run_id, created_at)"
        )


def new_run_id() -> str:
    """Generate a batch run id shared by every contact in one submission."""
    return uuid.uuid4().hex[:12]


def _row_to_item(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "contact_name": row["contact_name"],
        "status": row["status"],
        "created_at": row["created_at"],
        "data": json.loads(row["data"]),
    }


def create_item(
    run_id: str, contact_name: str, data: dict, status: str = "pending_review"
) -> str:
    """Insert one contact's recommendation into a batch run; return its item id."""
    item_id = uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute(
            "INSERT INTO items (id, run_id, contact_name, status, data) VALUES (?,?,?,?,?)",
            (item_id, run_id, contact_name, status, json.dumps(data)),
        )
    return item_id


def get_item(item_id: str) -> dict | None:
    """Fetch one contact recommendation by item id."""
    with connect() as c:
        row = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return _row_to_item(row) if row else None


def update_item(
    item_id: str, *, status: str | None = None, data: dict | None = None
) -> None:
    sets, args = [], []
    if status is not None:
        sets.append("status=?")
        args.append(status)
    if data is not None:
        sets.append("data=?")
        args.append(json.dumps(data))
    if not sets:
        return
    args.append(item_id)
    with connect() as c:
        c.execute(f"UPDATE items SET {', '.join(sets)} WHERE id=?", args)


def get_batch(run_id: str) -> list[dict]:
    """All contact items in one batch run, oldest first."""
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM items WHERE run_id=? ORDER BY created_at, rowid", (run_id,)
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def list_batches(limit: int = 20) -> list[dict]:
    """Recent batch runs (newest first) with lightweight per-contact summaries."""
    with connect() as c:
        run_ids = c.execute(
            "SELECT run_id, MAX(created_at) AS ts FROM items "
            "GROUP BY run_id ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in run_ids:
            rows = c.execute(
                "SELECT id, contact_name, status FROM items WHERE run_id=? ORDER BY created_at, rowid",
                (r["run_id"],),
            ).fetchall()
            out.append(
                {
                    "run_id": r["run_id"],
                    "created_at": r["ts"],
                    "contacts": [
                        {
                            "item_id": x["id"],
                            "contact_name": x["contact_name"],
                            "status": x["status"],
                        }
                        for x in rows
                    ],
                }
            )
    return out
