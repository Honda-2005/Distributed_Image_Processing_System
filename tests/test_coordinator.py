import io

import pytest
from fastapi.testclient import TestClient

from app.coordinator.main import app
from app.coordinator.job_manager import job_manager
from app.coordinator import routes


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    # Clear in-memory jobs before and after each test
    job_manager._jobs.clear()

    # Redirect input storage to a temporary folder
    base_dir = tmp_path
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(routes, "BASE_DIR", base_dir)
    monkeypatch.setattr(routes, "INPUT_DIR", input_dir)

    # Prevent real background dispatch during API tests
    monkeypatch.setattr(routes, "dispatch_job", lambda job_id: None)

    yield

    job_manager._jobs.clear()


def test_submit_single_job():
    files = [
        ("files", ("test.png", io.BytesIO(b"fake-image-data"), "image/png"))
    ]
    data = {"operation": "grayscale"}

    response = client.post("/jobs", files=files, data=data)

    assert response.status_code == 202
    body = response.json()
    assert body["total_jobs"] == 1
    assert len(body["job_ids"]) == 1

    job_id = body["job_ids"][0]

    job_response = client.get(f"/jobs/{job_id}")
    assert job_response.status_code == 200

    job = job_response.json()
    assert job["job_id"] == job_id
    assert job["operation"] == "grayscale"
    assert job["status"] == "pending"
    assert job["attempt_count"] == 0
    assert job["assigned_worker"] is None


def test_submit_multiple_jobs():
    files = [
        ("files", ("img1.png", io.BytesIO(b"img1"), "image/png")),
        ("files", ("img2.png", io.BytesIO(b"img2"), "image/png")),
        ("files", ("img3.png", io.BytesIO(b"img3"), "image/png")),
    ]
    data = {"operation": "blur"}

    response = client.post("/jobs", files=files, data=data)

    assert response.status_code == 202
    body = response.json()

    assert body["total_jobs"] == 3
    assert len(body["job_ids"]) == 3
    assert len(set(body["job_ids"])) == 3


def test_list_jobs():
    files = [
        ("files", ("test.png", io.BytesIO(b"fake-image-data"), "image/png"))
    ]
    data = {"operation": "threshold"}

    client.post("/jobs", files=files, data=data)

    response = client.get("/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] == 1
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["operation"] == "threshold"


def test_get_missing_job():
    response = client.get("/jobs/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_reject_non_image_upload():
    files = [
        ("files", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))
    ]
    data = {"operation": "grayscale"}

    response = client.post("/jobs", files=files, data=data)

    assert response.status_code == 400
    assert "not an image" in response.json()["detail"]


def test_reject_empty_upload():
    files = [
        ("files", ("empty.png", io.BytesIO(b""), "image/png"))
    ]
    data = {"operation": "grayscale"}

    response = client.post("/jobs", files=files, data=data)

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_reject_unsupported_operation():
    files = [
        ("files", ("test.png", b"image-data", "image/png"))
    ]

    response = client.post(
        "/jobs",
        files=files,
        data={"operation": "invalid_operation"},
    )

    assert response.status_code == 422


def test_reject_oversized_image():
    oversized_image = b"x" * (routes.MAX_IMAGE_BYTES + 1)

    files = [
        ("files", ("large.png", oversized_image, "image/png"))
    ]

    response = client.post(
        "/jobs",
        files=files,
        data={"operation": "grayscale"},
    )

    assert response.status_code == 413


def test_reject_oversized_batch():
    files = [
        ("files", (f"image_{i}.png", b"image", "image/png"))
        for i in range(routes.MAX_BATCH_SIZE + 1)
    ]

    response = client.post(
        "/jobs",
        files=files,
        data={"operation": "blur"},
    )

    assert response.status_code == 400


def test_reject_missing_files():
    response = client.post(
        "/jobs",
        data={"operation": "grayscale"},
    )

    assert response.status_code == 422


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "coordinator"


from app.coordinator.job_manager import JobManager
from app.common.schemas import Job
from app.common.constants import JobStatus


@pytest.fixture
def lifecycle_job():
    manager = JobManager()

    job = manager.create_job(
        Job(
            original_filename="test.png",
            operation="grayscale",
            input_ref="data/inputs/test.png",
        )
    )

    return manager, job


def test_successful_job_lifecycle(lifecycle_job):
    manager, job = lifecycle_job

    assert job.status == JobStatus.PENDING

    running = manager.start_job(job.job_id, "worker-1")

    assert running.status == JobStatus.RUNNING
    assert running.attempt_count == 1
    assert running.started_at is not None

    completed = manager.complete_job(
        job.job_id,
        "data/outputs/test.png",
        running.attempt_count,
    )

    assert completed.status == JobStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.result_ref is not None


def test_failed_job_lifecycle(lifecycle_job):
    manager, job = lifecycle_job

    running = manager.start_job(job.job_id, "worker-1")

    failed = manager.fail_job(
        job.job_id,
        "WORKER_TIMEOUT",
        "Worker did not respond.",
        running.attempt_count,
    )

    assert failed.status == JobStatus.FAILED
    assert failed.error.code == "WORKER_TIMEOUT"
    assert failed.completed_at is not None


def test_prevent_completion_of_pending_job(lifecycle_job):
    manager, job = lifecycle_job

    with pytest.raises(ValueError):
        manager.complete_job(
            job.job_id,
            "data/outputs/test.png",
            0,
        )


def test_prevent_duplicate_completion(lifecycle_job):
    manager, job = lifecycle_job

    running = manager.start_job(job.job_id, "worker-1")

    manager.complete_job(
        job.job_id,
        "data/outputs/test.png",
        running.attempt_count,
    )

    with pytest.raises(ValueError):
        manager.complete_job(
            job.job_id,
            "data/outputs/duplicate.png",
            running.attempt_count,
        )


def test_prevent_duplicate_start(lifecycle_job):
    manager, job = lifecycle_job

    manager.start_job(job.job_id, "worker-1")

    with pytest.raises(ValueError):
        manager.start_job(job.job_id, "worker-2")


def test_job_requeue(lifecycle_job):
    manager, job = lifecycle_job

    running = manager.start_job(job.job_id, "worker-1")

    pending = manager.requeue_job(
        job.job_id,
        running.attempt_count,
    )

    assert pending.status == JobStatus.PENDING
    assert pending.assigned_worker is None
    assert pending.attempt_count == 1

    reassigned = manager.start_job(job.job_id, "worker-2")

    assert reassigned.status == JobStatus.RUNNING
    assert reassigned.attempt_count == 2
    assert reassigned.assigned_worker == "worker-2"


def test_reject_outdated_worker_response(lifecycle_job):
    manager, job = lifecycle_job

    first = manager.start_job(job.job_id, "worker-1")

    manager.requeue_job(job.job_id, first.attempt_count)

    second = manager.start_job(job.job_id, "worker-2")

    with pytest.raises(ValueError):
        manager.complete_job(
            job.job_id,
            "data/outputs/outdated.png",
            first.attempt_count,
        )

    completed = manager.complete_job(
        job.job_id,
        "data/outputs/valid.png",
        second.attempt_count,
    )

    assert completed.status == JobStatus.COMPLETED
    assert completed.attempt_count == 2
