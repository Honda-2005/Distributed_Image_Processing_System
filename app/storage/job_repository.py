"""Save and load jobs and their events (Member 5)."""
from datetime import datetime, timezone
from pathlib import Path

from app.common.constants import JobStatus
from app.common.schemas import Job
from app.storage.database import get_connection, initialize_database

# Insert a new job, or update it if the ID already exists.
# The WHERE clause ignores late or outdated updates.
UPSERT_JOB = """
INSERT INTO jobs (
    job_id, original_filename, operation, input_ref, status, assigned_worker,
    attempt_count, created_at, started_at, completed_at, result_ref,
    error_code, error_message
) VALUES (
    :job_id, :original_filename, :operation, :input_ref, :status, :assigned_worker,
    :attempt_count, :created_at, :started_at, :completed_at, :result_ref,
    :error_code, :error_message
)
ON CONFLICT (job_id) DO UPDATE SET
    status = excluded.status,
    assigned_worker = excluded.assigned_worker,
    attempt_count = excluded.attempt_count,
    started_at = excluded.started_at,
    completed_at = excluded.completed_at,
    result_ref = excluded.result_ref,
    error_code = excluded.error_code,
    error_message = excluded.error_message
WHERE jobs.status NOT IN ('completed', 'failed')
  AND (
      excluded.attempt_count > jobs.attempt_count
      OR (
          excluded.attempt_count = jobs.attempt_count
          AND NOT (jobs.status = 'pending' AND excluded.status = 'running')
      )
  )
"""

INSERT_EVENT = """
INSERT INTO job_events (job_id, event_type, worker_id, attempt, details, created_at)
VALUES (?, ?, ?, ?, ?, ?)
"""


def _to_row(job: Job) -> dict:
    """Convert a Job object into database column values."""
    row = job.model_dump(mode="json")  # enums and dates become text
    error = row.pop("error")
    row["error_code"] = error["code"] if error else None
    row["error_message"] = error["message"] if error else None
    return row


def _to_job(row) -> Job:
    """Convert a database row back into a Job object."""
    data = dict(row)
    code = data.pop("error_code")
    message = data.pop("error_message")
    data["error"] = {"code": code, "message": message} if code is not None else None
    return Job.model_validate(data)


def save_job(
    job: Job,
    event_type: str | None = None,
    details: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Store the job's latest state and, optionally, one event.

    Returns False if the update was outdated and therefore ignored.
    """
    with get_connection(db_path) as db:
        db.execute("BEGIN IMMEDIATE")  # one writer at a time for these steps
        previous = db.execute(
            "SELECT assigned_worker FROM jobs WHERE job_id = ?", (job.job_id,)
        ).fetchone()

        if db.execute(UPSERT_JOB, _to_row(job)).rowcount == 0:
            return False

        if event_type:
            # A requeued job has no worker, so keep the one it had before.
            worker_id = job.assigned_worker or (
                previous["assigned_worker"] if previous else None
            )
            db.execute(
                INSERT_EVENT,
                (
                    job.job_id,
                    event_type,
                    worker_id,
                    job.attempt_count,
                    details,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
    return True


def get_job(job_id: str, db_path: Path | None = None) -> Job | None:
    """Return one job, or None if the ID is unknown."""
    with get_connection(db_path) as db:
        row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _to_job(row) if row else None


def list_jobs(
    status: JobStatus | None = None, db_path: Path | None = None
) -> list[Job]:
    """Return jobs from oldest to newest, optionally filtered by status."""
    query = "SELECT * FROM jobs"
    values: tuple = ()
    if status:
        query += " WHERE status = ?"
        values = (status.value,)

    with get_connection(db_path) as db:
        rows = db.execute(query + " ORDER BY created_at", values).fetchall()
    return [_to_job(row) for row in rows]


def get_events(job_id: str | None = None, db_path: Path | None = None) -> list[dict]:
    """Return events in the order they happened, for one job or for all jobs."""
    query = "SELECT * FROM job_events"
    values: tuple = ()
    if job_id:
        query += " WHERE job_id = ?"
        values = (job_id,)

    with get_connection(db_path) as db:
        rows = db.execute(query + " ORDER BY event_id", values).fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    # Self-check using a temporary database; your real jobs.db is not touched.
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        test_db = Path(folder) / "test.db"
        initialize_database(test_db)

        job = Job(original_filename="cat.png", operation="canny",
                  input_ref="data/inputs/cat.png")
        save_job(job, "created", db_path=test_db)

        job.status, job.assigned_worker, job.attempt_count = JobStatus.RUNNING, "worker-1", 1
        save_job(job, "started", db_path=test_db)

        job.status, job.result_ref = JobStatus.COMPLETED, "data/outputs/cat.png"
        save_job(job, "completed", db_path=test_db)

        late = job.model_copy(update={"status": JobStatus.RUNNING})
        print("Late update accepted:", save_job(late, "started", db_path=test_db))
        print("Stored status:", get_job(job.job_id, db_path=test_db).status.value)
        print("Events:", [e["event_type"] for e in get_events(db_path=test_db)])