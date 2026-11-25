"""Known workers and their health. Shared by Member 1 (coordinator), 3 (scheduler), 4 (fault tolerance).

Pure Python, no HTTP: Member 4's health checker calls mark_up/mark_down,
the scheduler only reads. Agree on this file before anyone changes it.
"""
import threading
from dataclasses import dataclass


@dataclass
class WorkerInfo:
    worker_id: str        # e.g. "worker-1"
    url: str              # e.g. "http://127.0.0.1:8001"
    available: bool = True
    in_flight: int = 0    # jobs sent to this worker and not finished yet


class WorkerRegistry:
    def __init__(self):
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = threading.Lock()

    def register(self, worker_id: str, url: str) -> None:
        with self._lock:
            self._workers[worker_id] = WorkerInfo(worker_id, url)

    def mark_down(self, worker_id: str) -> None:   # called by fault tolerance
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].available = False

    def mark_up(self, worker_id: str) -> None:     # called by fault tolerance
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].available = True

    def job_started(self, worker_id: str) -> None:   # coordinator calls after dispatch
        with self._lock:
            self._workers[worker_id].in_flight += 1

    def job_finished(self, worker_id: str) -> None:  # coordinator calls on success OR failure
        with self._lock:
            w = self._workers[worker_id]
            w.in_flight = max(0, w.in_flight - 1)

    def get(self, worker_id: str) -> WorkerInfo | None:
        return self._workers.get(worker_id)

    def all(self) -> list[WorkerInfo]:
        """Snapshot, ordered by worker_id so round-robin is stable."""
        with self._lock:
            return sorted(
                (WorkerInfo(**vars(w)) for w in self._workers.values()),
                key=lambda w: w.worker_id,
            )

    def available(self) -> list[WorkerInfo]:
        return [w for w in self.all() if w.available]
