"""pass^k and pass@k metrics."""
from __future__ import annotations
from math import comb
from typing import Any


def _safe_comb(n: int, k: int) -> int:
    if n < 0 or k < 0 or k > n:
        return 0
    return comb(n, k)


def pass_hat_k(successes: int, trials: int, k: int) -> float:
    """pass^k: expected fraction of k-subsets where all succeed."""
    if trials < k or k <= 0:
        return 0.0
    denom = _safe_comb(trials, k)
    if denom == 0:
        return 0.0
    return _safe_comb(successes, k) / denom


def pass_at_k(successes: int, trials: int, k: int) -> float:
    """pass@k: probability that at least one in k attempts succeeds."""
    if trials < k or k <= 0:
        return 0.0
    failures = trials - successes
    denom = _safe_comb(trials, k)
    if denom == 0:
        return 0.0
    if failures < k:
        return 1.0
    return 1.0 - _safe_comb(failures, k) / denom


def compute_metrics(
    results_by_task: dict[str, list[dict[str, Any]]],
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Aggregate metrics over all tasks.

    results_by_task: {task_id: [EpisodeResult-like dicts]}
    """
    if k_values is None:
        k_values = [1, 2, 3]

    per_task: list[dict[str, Any]] = []
    for task_id, trials in results_by_task.items():
        n = len(trials)
        c = sum(1 for t in trials if t.get("reward", 0) == 1)
        row: dict[str, Any] = {"task_id": task_id, "n": n, "successes": c}
        for k in k_values:
            row[f"pass_hat_{k}"] = pass_hat_k(c, n, k)
            row[f"pass_at_{k}"] = pass_at_k(c, n, k)
        per_task.append(row)

    aggregated: dict[str, Any] = {}
    for k in k_values:
        hat_vals = [r[f"pass_hat_{k}"] for r in per_task]
        at_vals = [r[f"pass_at_{k}"] for r in per_task]
        aggregated[f"pass_hat_{k}"] = _mean(hat_vals)
        aggregated[f"pass_at_{k}"] = _mean(at_vals)

    all_trials = [t for trials in results_by_task.values() for t in trials]
    if all_trials:
        aggregated["avg_turns"] = _mean([t.get("turns", 0) for t in all_trials])
        aggregated["avg_tool_calls"] = _mean([t.get("tool_calls", 0) for t in all_trials])
        total = len(all_trials)
        invalid = sum(t.get("invalid_tool_calls", 0) for t in all_trials)
        total_tools = sum(t.get("tool_calls", 0) for t in all_trials)
        aggregated["invalid_tool_call_rate"] = (invalid / total_tools) if total_tools > 0 else 0.0
        max_turn_failures = sum(1 for t in all_trials if t.get("failure_reason") == "max_turns_exceeded")
        aggregated["max_turn_failure_rate"] = max_turn_failures / total
        tool_errors = sum(1 for t in all_trials if t.get("failure_reason") == "tool_error")
        aggregated["tool_error_rate"] = tool_errors / total
        latencies = [t["latency_seconds"] for t in all_trials if t.get("latency_seconds") is not None]
        aggregated["mean_latency_seconds"] = _mean(latencies) if latencies else None

    aggregated["per_task"] = per_task
    return aggregated


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
