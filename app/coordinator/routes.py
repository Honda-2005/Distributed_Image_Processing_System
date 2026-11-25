from fastapi import BackgroundTasks
from app.coordinator.dispatcher import dispatch_job
from uuid import uuid4
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.common.config import BASE_DIR, INPUT_DIR
from app.common.constants import ImageOperation, MAX_IMAGE_BYTES
from app.common.schemas import (
    Job,
    JobSubmissionResponse,
    JobListResponse,
)
from app.coordinator.job_manager import job_manager


router = APIRouter(prefix="/jobs", tags=["Jobs"])

MAX_BATCH_SIZE = 50
MAX_BATCH_BYTES = 100 * 1024 * 1024


# Submit one or multiple image-processing jobs
@router.post(
    "",
    response_model=JobSubmissionResponse,
    status_code=202,
)

def submit_jobs(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    operation: ImageOperation = Form(...),
):
  
    if not files:
        raise HTTPException(400, "No images uploaded.")

    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(400, "Too many images in one batch.")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    new_jobs = []
    saved_files = []
    total_bytes = 0

    try:
        for file in files:

            # Validate the uploaded file
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(
                    400,
                    f"{file.filename} is not an image."
                )

            image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)

            if not image_bytes:
                raise HTTPException(
                    400,
                    f"{file.filename} is empty."
                )

            if len(image_bytes) > MAX_IMAGE_BYTES:
                raise HTTPException(
                    413,
                    f"{file.filename} exceeds the 15 MB limit."
                )

            total_bytes += len(image_bytes)

            if total_bytes > MAX_BATCH_BYTES:
                raise HTTPException(
                    413, "Batch exceeds the 100 MB limit."
                )

            # Generate a unique job ID
            job_id = str(uuid4())

            original_filename = Path(
                file.filename or "image"
            ).name

            extension = Path(original_filename).suffix.lower()

            if extension not in {
                ".png", ".jpg", ".jpeg", ".bmp",
                ".webp", ".tiff", ".tif"
            }:
                extension = ".img"

            # Store the input image safely
            input_path = INPUT_DIR / f"{job_id}{extension}"

            saved_files.append(input_path)
            input_path.write_bytes(image_bytes)

            # Construct the job
            job = Job(
                job_id=job_id,
                original_filename=original_filename,
                operation=operation,
                input_ref=input_path.relative_to(BASE_DIR).as_posix(),
            )

            new_jobs.append(job)

    except Exception:
        # Remove saved files if batch validation fails
        for path in saved_files:
            path.unlink(missing_ok=True)
        raise

    
    # Register jobs after validating the entire batch
    for job in new_jobs:
        job_manager.create_job(job)

    # Dispatch jobs for background processing
    for job in new_jobs:
        background_tasks.add_task(
            dispatch_job,
            job.job_id,
        )

    return JobSubmissionResponse(
        job_ids=[job.job_id for job in new_jobs],
        total_jobs=len(new_jobs),
    )



# Retrieve all jobs
@router.get("", response_model=JobListResponse)
def list_jobs():
    jobs = job_manager.get_all_jobs()

    return JobListResponse(
        jobs=jobs,
        total_jobs=len(jobs),
    )


# Retrieve a specific job
@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = job_manager.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    return job
