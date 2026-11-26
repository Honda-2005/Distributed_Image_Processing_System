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


def _read_runs(path: Path) -> tuple[list[dict], dict]:
    """Load one benchmark CSV file: its runs and its first row."""
    import csv

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    runs = []
    for row in rows:
        jobs = (part.split("=") for part in row["distribution"].split("; "))
        runs.append({
            "workers": int(row["workers"]),
            "elapsed_s": float(row["elapsed_s"]),
            "failed": int(row["failed"]),
            "throughput": float(row["throughput"]),
            "distribution": {name: int(count) for name, count in jobs},
        })
    return runs, rows[0]


def render_metrics_view(results_dir: Path | None = None) -> None:
    """Show measured benchmark results. The main dashboard can call this."""
    from app.common.config import OUTPUT_DIR

    # Reuse the benchmark's calculations so both show the same numbers.
    scripts_dir = str(PROJECT_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(1, scripts_dir)
    from benchmark import summarise

    st.header("Performance")
    files = sorted(
        Path(results_dir or OUTPUT_DIR).glob("benchmark_*.csv"), reverse=True
    )
    if not files:
        st.info("No results yet. Run: python scripts/benchmark.py")
        return

    path = st.selectbox(
        "Benchmark file (newest first)", files, format_func=lambda f: f.name
    )
    try:
        runs, first = _read_runs(path)
        summary = summarise(runs)
        repeats = int(first["repeats"])
        conditions = (
            f"Operation: {first['operation']} | Images: {first['images']} "
            f"({first['image_source']}) | Repeats: {repeats} | "
            f"Jobs in flight per worker: {first['jobs_in_flight_per_worker']} | "
            f"Workers on: {first['workers_location']} | "
            f"CPUs: {first['client_logical_cpus']} | {first['date']}"
        )
    except (OSError, KeyError, IndexError, ValueError):
        st.warning(f"Could not read {path.name}.")
        return

    st.caption(conditions)
    if repeats < 3:
        st.warning("Fewer than 3 repeats: treat this as a check, not a final result.")
    if any(row["failed"] for row in summary):
        st.warning("Some jobs failed, so speedup is not shown for every row.")

    st.table([
        {
            "Workers": str(row["workers"]),
            "Median time (s)": f"{row['median_s']:.3f}",
            "Throughput (jobs/s)": f"{row['throughput']:.2f}",
            "Speedup": f"{row['speedup']:.2f}" if row["speedup"] else "n/a",
            "Failed": str(row["failed"]),
            "Jobs per worker": row["jobs"],
        }
        for row in summary
    ])

    labels = [str(row["workers"]) for row in summary]
    left, right = st.columns(2)
    for column, title, key in (
        (left, "Median time (s)", "median_s"),
        (right, "Throughput (jobs/s)", "throughput"),
    ):
        with column:
            st.subheader(title)
            st.bar_chart(
                {"Workers": labels, title: [row[key] for row in summary]},
                x="Workers",
                y=title,
            )


if __name__ == "__main__":
    # Preview with sample jobs:  streamlit run frontend/components.py -- --demo
    st.set_page_config(page_title="Results and performance", layout="wide")
    gallery_tab, metrics_tab = st.tabs(["Results gallery", "Performance"])
    with gallery_tab:
        if "--demo" in sys.argv:
            demo_db, demo_folder = _create_demo_data()
            render_results_gallery(demo_db, demo_folder)
        else:
            render_results_gallery()
    with metrics_tab:
        render_metrics_view()