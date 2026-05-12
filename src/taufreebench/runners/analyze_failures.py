"""Analyze failure modes across benchmark results."""
from __future__ import annotations
from collections import defaultdict
from typing import Any


FAILURE_GROUPS = [
    "wrong_database_state",
    "missing_required_output",
    "max_turns_exceeded",
    "tool_error",
    "invalid_tool_call",
    "parser_failure",
    "exception",
]


def analyze_failures(results_by_task: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trials = [t for trials in results_by_task.values() for t in trials]
    failed = [t for t in all_trials if t.get("reward", 0) == 0]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in failed:
        group = _classify(trial)
        groups[group].append(trial)

    total = len(all_trials)
    return {
        "total_trials": total,
        "total_failures": len(failed),
        "failure_rate": len(failed) / total if total > 0 else 0.0,
        "groups": {k: {"count": len(v), "task_ids": list({t.get("task_id", "?") for t in v})} for k, v in groups.items()},
    }


def _classify(trial: dict[str, Any]) -> str:
    reason = trial.get("failure_reason", "") or ""
    if "max_turns" in reason:
        return "max_turns_exceeded"
    if "tool_error" in reason:
        return "tool_error"
    if "parser" in reason or "parse" in reason:
        return "parser_failure"
    if reason and reason not in ("", "None"):
        return "exception"
    # Check specific reward components
    if trial.get("action_reward", 1) == 0:
        return "wrong_database_state"
    if trial.get("output_reward", 1) == 0:
        return "missing_required_output"
    if trial.get("invalid_tool_calls", 0) > 0:
        return "invalid_tool_call"
    return "wrong_database_state"
