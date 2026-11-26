
import logging

import httpx

from app.common.config import (
    BASE_DIR,
    OUTPUT_DIR,
    WORKER_URLS,
)
from app.common.constants import JobStatus
from app.coordinator.job_manager import job_manager
from app.coordinator.worker_client import WorkerClient


logger = logging.getLogger(__name__)


def dispatch_job(job_id: str):

    job = job_manager.get_job(job_id)

    if job is None or job.status != JobStatus.PENDING:
        return

    # Temporary single-worker selection
    # Member 3's scheduler will replace this later
    if not WORKER_URLS:
        logger.warning("No workers configured.")
        return

    worker_url = WORKER_URLS[0]
    client = WorkerClient(worker_url)

    try:
        health = client.health_check()
        worker_id = health["worker_id"]

    except Exception as exc:
        # Record an unsuccessful attempt
        try:
            job = job_manager.start_job(job_id, worker_url)
            job_manager.fail_job(
                job_id,
                "WORKER_UNAVAILABLE",
                str(exc),
                job.attempt_count,
            )
        except ValueError:
            pass
        return

    try:
        job = job_manager.start_job(job_id, worker_id)
    except ValueError:
        return

    attempt = job.attempt_count
    output_path = None

    try:
        input_path = BASE_DIR / job.input_ref

        print(
            f"[DISPATCHER] Processing {job_id} "
            f"using {worker_id}"
        )

        result_bytes, actual_worker = client.process_image(
            input_path,
            job.operation,
        )

        if actual_worker != worker_id:
            raise ValueError("Worker identity changed.")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = (
            OUTPUT_DIR / f"{job_id}_{attempt}.png"
        )

        output_path.write_bytes(result_bytes)

        result_ref = output_path.relative_to(
            BASE_DIR
        ).as_posix()

        job_manager.complete_job(
            job_id,
            result_ref,
            attempt,
        )

        print(f"[DISPATCHER] Completed {job_id}")

    except Exception as exc:

        if output_path is not None:
            output_path.unlink(missing_ok=True)

        error_code = (
            "WORKER_TIMEOUT"
            if isinstance(exc, httpx.TimeoutException)
            else "PROCESSING_ERROR"
        )

        try:
            job_manager.fail_job(
                job_id,
                error_code,
                str(exc),
                attempt,
            )
        except ValueError:
            logger.warning("Ignoring outdated job failure.")

        print(f"[DISPATCHER] Failed {job_id}: {exc}")
