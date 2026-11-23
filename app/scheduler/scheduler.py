"""Worker selection (Member 3).

The coordinator calls `scheduler.select_worker()` for each pending job.
It returns a WorkerInfo, or None when no worker is available
(the coordinator should then leave the job PENDING and try again later).
"""
import threading

from app.coordinator.worker_registry import WorkerInfo, WorkerRegistry

ROUND_ROBIN = "round_robin"
LEAST_LOADED = "least_loaded"   # fewest in-flight jobs; ties broken round-robin


class Scheduler:
    def __init__(self, registry: WorkerRegistry, policy: str = ROUND_ROBIN):
        if policy not in (ROUND_ROBIN, LEAST_LOADED):
            raise ValueError(f"unknown policy: {policy}")
        self.registry = registry
        self.policy = policy
        self._last_id: str | None = None
        self._lock = threading.Lock()

    def select_worker(self) -> WorkerInfo | None:
        with self._lock:
            workers = self.registry.available()
            if not workers:
                return None

            # Rotate the list so it starts right after the last worker we picked.
            # Works even if workers join/leave between calls.
            start = 0
            if self._last_id is not None:
                after = [i for i, w in enumerate(workers) if w.worker_id > self._last_id]
                start = after[0] if after else 0
            ordered = workers[start:] + workers[:start]

            if self.policy == LEAST_LOADED:
                chosen = min(ordered, key=lambda w: w.in_flight)  # min keeps first on ties
            else:
                chosen = ordered[0]

            self._last_id = chosen.worker_id
            return chosen
