
from datetime import datetime, timezone
from threading import Lock

from app.common.constants import JobStatus
from app.common.schemas import Job, JobError


class JobManager:

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    # Register a newly created job
    def create_job(self, job: Job) -> Job:
        with self._lock:
            if job.job_id in self._jobs:
                raise ValueError("Job ID already exists.")

            if job.status != JobStatus.PENDING:
                raise ValueError("New jobs must be pending.")

            self._jobs[job.job_id] = job.model_copy(deep=True)
            return self._jobs[job.job_id].model_copy(deep=True)

    # Retrieve a specific job
    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    # Retrieve all jobs
    def get_all_jobs(self) -> list[Job]:
        with self._lock:
            return [
                job.model_copy(deep=True)
                for job in self._jobs.values()
            ]

    # Mark a job as running
    def start_job(
        self, job_id: str, worker_id: str
    ) -> Job:
        with self._lock:
            job = self._jobs[job_id]

            if job.status != JobStatus.PENDING:
                raise ValueError("Only pending jobs can start.")

            job.status = JobStatus.RUNNING
            job.assigned_worker = worker_id
            job.attempt_count += 1
            job.started_at = datetime.now(timezone.utc)
            job.completed_at = None
            job.error = None

            return job.model_copy(deep=True)

    # Mark a job as successfully completed
    def complete_job(
        self, job_id: str, result_ref: str, attempt: int
    ) -> Job:
        with self._lock:
            job = self._jobs[job_id]

            if (
                job.status != JobStatus.RUNNING
                or job.attempt_count != attempt
            ):
                raise ValueError("Invalid or outdated job completion.")

            job.status = JobStatus.COMPLETED
            job.result_ref = result_ref
            job.completed_at = datetime.now(timezone.utc)
            job.error = None

            return job.model_copy(deep=True)

    # Mark a job as failed
    def fail_job(
        self, job_id: str, code: str,
        message: str, attempt: int
    ) -> Job:
        with self._lock:
            job = self._jobs[job_id]

            if (
                job.status != JobStatus.RUNNING
                or job.attempt_count != attempt
            ):
                raise ValueError("Invalid or outdated job failure.")

            job.status = JobStatus.FAILED
            job.result_ref = None
            job.error = JobError(code=code, message=message)
            job.completed_at = datetime.now(timezone.utc)

            return job.model_copy(deep=True)

    # Return a running job to the pending queue
    def requeue_job(self, job_id: str, attempt: int) -> Job:
        with self._lock:
            job = self._jobs[job_id]

            if (
                job.status != JobStatus.RUNNING
                or job.attempt_count != attempt
            ):
                raise ValueError("Invalid or outdated retry.")

            job.status = JobStatus.PENDING
            job.assigned_worker = None
            job.started_at = None
            job.completed_at = None
            job.result_ref = None
            job.error = None

            return job.model_copy(deep=True)


# Shared coordinator instance
job_manager = JobManager()
