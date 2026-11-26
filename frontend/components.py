"""Dashboard components: results gallery (Member 5)."""
import sys
from pathlib import Path

# Streamlit puts frontend/ first on the import path, where "app" would mean
# frontend/app.py. Put the project root first so "app" means the app/ package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from PIL import Image

from app.common.constants import JobStatus
from app.common.schemas import Job
from app.storage import job_repository as repo
from app.storage.database import initialize_database

JOBS_PER_PAGE = 10


def _show_image(base_dir: Path, ref: str | None, caption: str) -> None:
    """Show one stored image, or explain why it cannot be shown."""
    if not ref:
        st.info(f"{caption}: not available yet.")
        return
    try:
        with Image.open(base_dir / ref) as image:
            st.image(image.convert("RGBA"), caption=caption, width="stretch")
    except (OSError, ValueError):
        st.warning(f"{caption}: file is missing or unreadable ({ref}).")


def _show_summary(jobs: list[Job]) -> None:
    """Show the total number of jobs and the count for each status."""
    columns = st.columns(len(JobStatus) + 1)
    columns[0].metric("Total", len(jobs))
    for column, status in zip(columns[1:], JobStatus):
        count = sum(job.status == status for job in jobs)
        column.metric(status.value.title(), count)


def _show_job(job: Job, base_dir: Path, db_path: Path | None) -> None:
    """Show one job: details, error, both images and history."""
    with st.container(border=True):
        st.text(job.original_filename)

        details = [
            f"Status: {job.status.value}",
            f"Operation: {job.operation.value}",
            f"Worker: {job.assigned_worker or 'not assigned'}",
            f"Attempts: {job.attempt_count}",
        ]
        if job.started_at and job.completed_at:
            seconds = (job.completed_at - job.started_at).total_seconds()
            details.append(f"Last attempt: {seconds:.2f} s")
        st.caption(" | ".join(details))

        if job.error:
            st.error(f"{job.error.code}: {job.error.message}")

        original, processed = st.columns(2)
        with original:
            _show_image(base_dir, job.input_ref, "Original")
        with processed:
            _show_image(base_dir, job.result_ref, "Processed")

        events = repo.get_events(job.job_id, db_path=db_path)
        if events:
            with st.expander("History"):
                for event in events:
                    st.text(
                        f"{event['created_at']}  {event['event_type']}  "
                        f"attempt {event['attempt']}  "
                        f"{event['worker_id'] or ''}"
                    )


def render_results_gallery(
    db_path: Path | None = None, base_dir: Path = PROJECT_ROOT
) -> None:
    """Draw the results gallery. The main dashboard can call this function."""
    initialize_database(db_path)  # works even before the first job exists

    st.header("Results gallery")
    st.button("Refresh")  # any click reruns the page and reloads the data

    jobs = repo.list_jobs(db_path=db_path)
    if not jobs:
        st.info("No jobs yet.")
        return

    _show_summary(jobs)

    choice = st.selectbox(
        "Filter by status", ["all"] + [status.value for status in JobStatus]
    )
    shown = [job for job in jobs if choice in ("all", job.status.value)]
    if not shown:
        st.info("No jobs with this status.")
        return
    shown.reverse()  # newest first

    pages = (len(shown) - 1) // JOBS_PER_PAGE + 1
    page = 1
    if pages > 1:
        page = st.number_input("Page", min_value=1, max_value=pages, value=1)

    start = (page - 1) * JOBS_PER_PAGE
    for job in shown[start:start + JOBS_PER_PAGE]:
        _show_job(job, base_dir, db_path)


def _create_demo_data() -> tuple[Path, Path]:
    """Make sample jobs in a temporary folder to preview the gallery."""
    import tempfile

    import cv2
    import numpy as np

    folder = Path(tempfile.gettempdir()) / "gallery_demo"
    folder.mkdir(exist_ok=True)
    db_path = folder / "demo.db"
    initialize_database(db_path)

    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.circle(image, (160, 120), 80, (0, 165, 255), -1)
    cv2.imwrite(str(folder / "input.png"), image)
    cv2.imwrite(str(folder / "output.png"), cv2.Canny(image, 100, 200))

    def add(job_id: str, status: JobStatus, **fields) -> None:
        job = Job(job_id=job_id, original_filename=f"{job_id}.png",
                  operation="canny", input_ref="input.png",
                  status=status, **fields)
        repo.save_job(job, status.value, db_path=db_path)

    if not repo.list_jobs(db_path=db_path):
        add("demo-completed", JobStatus.COMPLETED, assigned_worker="worker-1",
            attempt_count=1, result_ref="output.png")
        add("demo-failed", JobStatus.FAILED, assigned_worker="worker-2",
            attempt_count=3,
            error={"code": "WORKER_TIMEOUT", "message": "Sample error."})
        add("demo-pending", JobStatus.PENDING)

    return db_path, folder


if __name__ == "__main__":
    # Preview with sample data:  streamlit run frontend/components.py -- --demo
    st.set_page_config(page_title="Results gallery", layout="wide")
    if "--demo" in sys.argv:
        demo_db, demo_folder = _create_demo_data()
        render_results_gallery(demo_db, demo_folder)
    else:
        render_results_gallery()