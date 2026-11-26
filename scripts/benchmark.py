"""Compare one worker with several workers on the same workload (Member 5).

Run from the project root:  python scripts/benchmark.py --workers 1 2 3

Jobs go straight to the workers over HTTP, using the team's scheduler.
The coordinator is not part of this measurement.
"""
import argparse
import csv
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import httpx
import numpy as np

from app.common.config import OUTPUT_DIR
from app.common.constants import ImageOperation
from app.coordinator.worker_client import WorkerClient
from app.coordinator.worker_registry import WorkerRegistry
from app.scheduler.scheduler import LEAST_LOADED, Scheduler

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def create_images(folder: Path, count: int, width: int, height: int) -> list[Path]:
    """Create the same synthetic images every time (fixed random seed)."""
    rng = np.random.default_rng(42)
    paths = []
    for number in range(count):
        image = np.full((height, width, 3), 40, dtype=np.uint8)
        for _ in range(200):
            center = (int(rng.integers(width)), int(rng.integers(height)))
            color = tuple(int(value) for value in rng.integers(0, 256, 3))
            radius = int(rng.integers(5, max(6, height // 8)))
            cv2.circle(image, center, radius, color, -1)
        path = folder / f"image_{number:03}.png"
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


def is_healthy(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=1, trust_env=False).is_success
    except httpx.HTTPError:
        return False


def start_workers(count: int, first_port: int, processes: list) -> list[str]:
    """Start worker services on this computer and wait until they respond."""
    urls = []
    for number in range(count):
        port = first_port + number
        url = f"http://127.0.0.1:{port}"
        if is_healthy(url):
            raise SystemExit(f"Port {port} is already in use. Try --port.")
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.worker.main:app",
             "--port", str(port), "--log-level", "warning", "--no-access-log"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
        )
        processes.append(process)

        deadline = time.monotonic() + 30
        while not is_healthy(url):
            if process.poll() is not None or time.monotonic() > deadline:
                raise SystemExit(f"Worker on port {port} did not start.")
            time.sleep(0.2)
        urls.append(url)
    return urls


def run_batch(
    urls: list[str], images: list[Path], operation: ImageOperation, in_flight: int
) -> dict:
    """Process every image once and measure the whole batch."""
    registry = WorkerRegistry()
    for number, url in enumerate(urls, start=1):
        registry.register(f"worker-{number}", url)
    scheduler = Scheduler(registry, policy=LEAST_LOADED)
    lock = threading.Lock()
    completed = Counter()
    busy = Counter()
    errors = []

    def process(path: Path) -> None:
        with lock:  # choose and reserve a worker in one step
            worker = scheduler.select_worker()
            registry.job_started(worker.worker_id)
        started = time.perf_counter()
        try:
            WorkerClient(worker.url).process_image(path, operation)
            outcome = None
        except Exception as exc:  # count the failure and keep going
            outcome = f"{path.name}: {exc}"
        duration = time.perf_counter() - started
        with lock:
            registry.job_finished(worker.worker_id)
            busy[worker.worker_id] += duration
            if outcome:
                errors.append(outcome)
            else:
                completed[worker.worker_id] += 1

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(urls) * in_flight) as pool:
        list(pool.map(process, images))
    elapsed = time.perf_counter() - start

    names = [worker.worker_id for worker in registry.all()]
    return {
        "workers": len(urls),
        "elapsed_s": elapsed,
        "completed": sum(completed.values()),
        "failed": len(errors),
        "throughput": sum(completed.values()) / elapsed,
        "distribution": {name: completed[name] for name in names},
        # Share of the batch time each worker's request slots were occupied.
        "utilisation": {name: busy[name] / (elapsed * in_flight) for name in names},
        "errors": errors,
    }


def summarise(runs: list[dict]) -> list[dict]:
    """Combine repeated runs: median time, throughput and speedup."""
    rows = []
    baseline = None
    for count in sorted({run["workers"] for run in runs}):
        group = [run for run in runs if run["workers"] == count]
        times = [run["elapsed_s"] for run in group]
        median = statistics.median(times)
        failed = sum(run["failed"] for run in group)
        if count == 1 and not failed:
            baseline = median
        jobs = Counter()
        for run in group:
            jobs.update(run["distribution"])
        rows.append({
            "workers": count,
            "median_s": median,
            "min_s": min(times),
            "max_s": max(times),
            "throughput": statistics.median(run["throughput"] for run in group),
            # A run with failures did less work, so it cannot be compared.
            "speedup": baseline / median if baseline and not failed else None,
            "failed": failed,
            "jobs": ", ".join(f"{name}: {total}" for name, total in sorted(jobs.items())),
        })
    return rows


def save_runs(runs: list[dict], conditions: dict) -> Path:
    """Write every individual run, with its conditions, to a CSV file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"benchmark_{datetime.now():%Y%m%d_%H%M%S}.csv"
    rows = []
    for run in runs:
        row = {key: value for key, value in run.items() if key != "errors"}
        row["distribution"] = "; ".join(
            f"{name}={jobs}" for name, jobs in run["distribution"].items())
        row["utilisation"] = "; ".join(
            f"{name}={share:.0%}" for name, share in run["utilisation"].items())
        rows.append({**row, **conditions})
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_report(rows: list[dict], conditions: dict) -> None:
    """Print Markdown that can be pasted into the evaluation document."""
    print("\n### Conditions\n")
    for key, value in conditions.items():
        print(f"- {key}: {value}")
    print("\n### Results\n")
    print("| Workers | Median time (s) | Range (s) | Throughput (jobs/s) "
          "| Speedup | Failed | Jobs per worker (all runs) |")
    print("|---|---|---|---|---|---|---|")
    for row in rows:
        speedup = f"{row['speedup']:.2f}" if row["speedup"] else "n/a"
        print(f"| {row['workers']} | {row['median_s']:.3f} "
              f"| {row['min_s']:.3f} - {row['max_s']:.3f} "
              f"| {row['throughput']:.2f} | {speedup} | {row['failed']} "
              f"| {row['jobs']} |")


def parse_arguments() -> argparse.Namespace:
    def positive(text: str) -> int:
        value = int(text)
        if value < 1:
            raise argparse.ArgumentTypeError("must be 1 or more")
        return value

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=positive, nargs="+", default=[1, 2, 3],
                        help="worker counts to compare (1 is always included)")
    parser.add_argument("--urls", nargs="+",
                        help="use already running workers instead of starting them")
    parser.add_argument("--images", type=Path, help="folder of your own images")
    parser.add_argument("--count", type=positive, default=30,
                        help="number of synthetic images")
    parser.add_argument("--width", type=positive, default=1920)
    parser.add_argument("--height", type=positive, default=1080)
    parser.add_argument("--operation", default="canny",
                        choices=[item.value for item in ImageOperation])
    parser.add_argument("--repeats", type=positive, default=3)
    parser.add_argument("--in-flight", type=positive, default=1,
                        help="jobs sent to each worker at the same time")
    parser.add_argument("--port", type=positive, default=8101,
                        help="first port for workers started by this script")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    counts = sorted({1, *args.workers})
    if args.urls and max(counts) > len(args.urls):
        raise SystemExit(f"{max(counts)} workers requested, "
                         f"but only {len(args.urls)} URLs given.")

    processes = []
    with tempfile.TemporaryDirectory() as folder:
        if args.images:
            images = sorted(path for path in args.images.glob("*")
                            if path.suffix.lower() in IMAGE_TYPES)
            if not images:
                raise SystemExit(f"No images found in {args.images}")
            source = f"files from {args.images.name}"
        else:
            print("Creating test images...")
            images = create_images(Path(folder), args.count, args.width, args.height)
            source = f"synthetic {args.width}x{args.height} PNG"

        operation = ImageOperation(args.operation)
        try:
            if args.urls:
                urls = [url.rstrip("/") for url in args.urls]
                for url in urls[:max(counts)]:
                    if not is_healthy(url):
                        raise SystemExit(f"Worker not responding: {url}")
            else:
                print("Starting workers...")
                urls = start_workers(max(counts), args.port, processes)

            # One untimed job per worker, so first-request delays are excluded.
            for url in urls[:max(counts)]:
                WorkerClient(url).process_image(images[0], operation)

            runs = []
            for repeat in range(1, args.repeats + 1):
                for count in counts:  # alternate counts to spread out drift
                    result = run_batch(urls[:count], images, operation, args.in_flight)
                    runs.append({"repeat": repeat, **result})
                    print(f"Run {repeat}, {count} worker(s): "
                          f"{result['elapsed_s']:.3f} s, "
                          f"{result['completed']} completed, {result['failed']} failed")
                    for error in result["errors"][:3]:
                        print("  ", error)
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                process.wait(timeout=10)

        conditions = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "operation": operation.value,
            "images": len(images),
            "image_source": source,
            "total_input_mb": round(sum(p.stat().st_size for p in images) / 1e6, 2),
            "jobs_in_flight_per_worker": args.in_flight,
            "repeats": args.repeats,
            "scheduling": "least_loaded",
            "workers_location": "external URLs" if args.urls else "same computer",
            "client_system": platform.platform(),
            "client_logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
            "opencv": cv2.__version__,
        }

    path = save_runs(runs, conditions)
    print_report(summarise(runs), conditions)
    print(f"\nAll runs saved to: {path}")


if __name__ == "__main__":
    main()