"""Run the full benchmark across all tasks."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from taufreebench.core.metrics import compute_metrics
from taufreebench.runners.run_episode import run_episode_for_task, _load_tasks, _get_data_dir


def run_benchmark(
    domain: str = "retail",
    agent_type: str = "rule",
    agent_model: str | None = None,
    user_type: str = "scripted",
    user_model: str | None = None,
    trials: int = 1,
    task_ids: list[str] | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    base_data_dir = _get_data_dir(domain, data_dir)
    all_tasks = _load_tasks(domain, base_data_dir)
    if task_ids:
        all_tasks = [t for t in all_tasks if t.id in task_ids]

    results_by_task: dict[str, list[dict[str, Any]]] = {}

    for task in all_tasks:
        results_by_task[task.id] = []
        for trial in range(trials):
            try:
                episode = run_episode_for_task(
                    domain=domain,
                    task_id=task.id,
                    agent_type=agent_type,
                    agent_model=agent_model,
                    user_type=user_type,
                    user_model=user_model,
                    data_dir=data_dir,
                )
                results_by_task[task.id].append(episode.model_dump())
            except Exception as e:
                results_by_task[task.id].append({
                    "task_id": task.id,
                    "reward": 0,
                    "action_reward": 0,
                    "output_reward": 0,
                    "turns": 0,
                    "tool_calls": 0,
                    "invalid_tool_calls": 0,
                    "failure_reason": str(e),
                    "latency_seconds": None,
                })

    return results_by_task
