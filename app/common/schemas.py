
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.common.constants import JobStatus, ImageOperation


class JobError(BaseModel):
    code: str
    message: str


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))

    original_filename: str
    operation: ImageOperation
    input_ref: str

    status: JobStatus = JobStatus.PENDING
    assigned_worker: str | None = None
    attempt_count: int = Field(default=0, ge=0)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None

    result_ref: str | None = None
    error: JobError | None = None


class JobSubmissionResponse(BaseModel):
    job_ids: list[str]
    total_jobs: int


class JobListResponse(BaseModel):
    jobs: list[Job]
    total_jobs: int
