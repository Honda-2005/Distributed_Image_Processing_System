from collections import Counter

import pytest

from app.coordinator.worker_registry import WorkerRegistry
from app.scheduler.scheduler import LEAST_LOADED, ROUND_ROBIN, Scheduler


def make_registry(n):
    reg = WorkerRegistry()
    for i in range(1, n + 1):
        reg.register(f"worker-{i}", f"http://127.0.0.1:800{i}")
    return reg


def pick_ids(sched, n):
    return [sched.select_worker().worker_id for _ in range(n)]


@pytest.mark.parametrize("n_workers", [1, 2, 3])
def test_round_robin_spreads_jobs_evenly(n_workers):
    sched = Scheduler(make_registry(n_workers))
    counts = Counter(pick_ids(sched, 30))
    assert len(counts) == n_workers
    assert set(counts.values()) == {30 // n_workers}


def test_round_robin_order():
    sched = Scheduler(make_registry(3))
    assert pick_ids(sched, 4) == ["worker-1", "worker-2", "worker-3", "worker-1"]


def test_unavailable_worker_never_selected():
    reg = make_registry(3)
    reg.mark_down("worker-2")
    sched = Scheduler(reg)
    assert "worker-2" not in pick_ids(sched, 20)


def test_worker_comes_back():
    reg = make_registry(2)
    reg.mark_down("worker-2")
    sched = Scheduler(reg)
    assert pick_ids(sched, 3) == ["worker-1"] * 3
    reg.mark_up("worker-2")
    assert "worker-2" in pick_ids(sched, 2)


def test_no_workers_returns_none():
    reg = make_registry(2)
    reg.mark_down("worker-1")
    reg.mark_down("worker-2")
    assert Scheduler(reg).select_worker() is None
    assert Scheduler(WorkerRegistry()).select_worker() is None


def test_least_loaded_prefers_idle_worker():
    reg = make_registry(3)
    reg.job_started("worker-1")
    reg.job_started("worker-1")
    reg.job_started("worker-2")
    sched = Scheduler(reg, policy=LEAST_LOADED)
    assert sched.select_worker().worker_id == "worker-3"


def test_least_loaded_ties_rotate():
    sched = Scheduler(make_registry(3), policy=LEAST_LOADED)
    assert pick_ids(sched, 3) == ["worker-1", "worker-2", "worker-3"]


def test_bad_policy_rejected():
    with pytest.raises(ValueError):
        Scheduler(WorkerRegistry(), policy="random")
