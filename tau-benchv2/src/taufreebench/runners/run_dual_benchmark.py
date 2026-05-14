"""Loop over all telecom tasks × trials, collecting `DualEpisodeResult`s."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def run_dual_benchmark(
    domain: str = "telecom",
    mode: str = "default",
    agent_type: str = "rule",
    agent_model: str | None = None,
    user_type: str = "scripted",
    user_model: str | None = None,
    trials: int = 1,
    task_ids: list[str] | None = None,
    verbose: bool = True,
    parallel: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    """Run the dual-control benchmark and return `{task_id: [episode_dict, ...]}`.

    `parallel` controls how many episodes run concurrently (threads — safe because
    workload is I/O-bound on API calls and each episode allocates its own DBs/state).
    """
    if domain != "telecom":
        raise ValueError(f"Only the 'telecom' domain is supported (got {domain!r}).")

    from taufreebench.runners.run_dual_episode import (
        load_telecom_tasks,
        run_dual_episode_for_task,
    )

    tasks = load_telecom_tasks()
    if task_ids:
        wanted = set(task_ids)
        tasks = [t for t in tasks if t.id in wanted]

    # Build a flat list of (task, trial_index, position) jobs so results land in order.
    jobs: list[tuple] = []
    for task in tasks:
        for trial in range(trials):
            jobs.append((task, trial))
    total = len(jobs)
    print_lock = threading.Lock()
    done = [0]
    results_by_task: dict[str, list] = {task.id: [None] * trials for task in tasks}

    def _run_one(task, trial_idx) -> tuple[str, int, dict[str, Any]]:
        try:
            episode = run_dual_episode_for_task(
                task_id=task.id, mode=mode,
                agent_type=agent_type, agent_model=agent_model,
                user_type=user_type, user_model=user_model,
            )
            return (task.id, trial_idx, episode.model_dump())
        except Exception as e:  # noqa: BLE001
            stub = _failed_stub(task.id, mode, agent_type, agent_model, user_type, user_model, e)
            return (task.id, trial_idx, stub)

    if parallel <= 1:
        for task, trial in jobs:
            tid, ti, ep = _run_one(task, trial)
            results_by_task[tid][ti] = ep
            done[0] += 1
            if verbose:
                print(f"  [{done[0]}/{total}] {tid} trial {ti + 1}", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = [pool.submit(_run_one, t, ti) for t, ti in jobs]
            for fut in as_completed(futures):
                tid, ti, ep = fut.result()
                results_by_task[tid][ti] = ep
                with print_lock:
                    done[0] += 1
                    if verbose:
                        print(f"  [{done[0]}/{total}] {tid} trial {ti + 1}", flush=True)

    # Filter out any None placeholders (shouldn't happen, but guard against it).
    final = {tid: [ep for ep in eps if ep is not None] for tid, eps in results_by_task.items()}
    return final


def _failed_stub(
    task_id: str,
    mode: str,
    agent_type: str,
    agent_model: str | None,
    user_type: str,
    user_model: str | None,
    exc: BaseException,
) -> dict[str, Any]:
    """Produce a minimal episode-like dict for a crashed trial."""
    return {
        "task_id": task_id,
        "reward": 0,
        "assertion_reward": 0,
        "output_reward": 0,
        "action_match_reward": None,
        "trajectory": [],
        "final_agent_db": {},
        "final_user_db": {},
        "expected_agent_db": None,
        "expected_user_db": None,
        "assertion_results": [],
        "db_diff": {},
        "compact_diff": {},
        "agent_messages": [],
        "user_messages": [],
        "failure_reason": f"runner_exception: {type(exc).__name__}: {exc}",
        "failure_class": "unknown_failure",
        "agent_provider": agent_type,
        "agent_model": agent_model,
        "user_provider": user_type,
        "user_model": user_model,
        "turns": 0,
        "agent_tool_calls": 0,
        "user_tool_calls": 0,
        "invalid_agent_tool_calls": 0,
        "invalid_user_tool_calls": 0,
        "agent_tool_errors": 0,
        "user_tool_errors": 0,
        "latency_seconds": None,
        "mode": mode,
    }
