"""SQLite setup for job metadata and events (Member 5).

Only text and numbers are stored here. Images stay in data/inputs and
data/outputs, and the database keeps their relative paths.
"""
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.common import config
from app.common.constants import ImageOperation, JobStatus


def _sql_list(enum_class) -> str:
    """Turn an Enum into a SQL value list, e.g. 'pending', 'running'."""
    return ", ".join(f"'{item.value}'" for item in enum_class)


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS jobs (
    job_id            TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    operation         TEXT NOT NULL CHECK (operation IN ({_sql_list(ImageOperation)})),
    input_ref         TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ({_sql_list(JobStatus)})),
    assigned_worker   TEXT,
    attempt_count     INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    completed_at      TEXT,
    result_ref        TEXT,
    error_code        TEXT,
    error_message     TEXT
);

CREATE TABLE IF NOT EXISTS job_events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    worker_id  TEXT,
    attempt    INTEGER NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events (job_id);
"""


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, then close.

    Each call gets its own connection, so it is safe to use from the
    coordinator's background threads.
    """
    path = Path(db_path or config.DATABASE_PATH)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row  # read columns by name
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:  # one transaction: commit or rollback
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: Path | None = None) -> None:
    """Create the database file, tables and indexes if they do not exist."""
    path = Path(db_path or config.DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(path) as connection:
        # Write-ahead logging lets the dashboard read while jobs are written.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)


if __name__ == "__main__":
    initialize_database()
    with get_connection() as db:
        rows = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    print("Database:", config.DATABASE_PATH)
    print("Tables:", [row["name"] for row in rows])