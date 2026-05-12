"""Analyze failure modes across benchmark results."""
from __future__ import annotations
from collections import defaultdict
from typing import Any


FAILURE_GROUPS = [
    "success",
    "invalid_task_annotation",
    "wrong_database_state_and_missing_output",
    "wrong_database_state",
    "missing_required_output",
    "max_turns_exceeded",
    "tool_error",
    "invalid_tool_call",
    "parser_failure",
    "unknown_failure",
]


def classify_failure(result: dict[str, Any]) -> str:
    """Classify a single episode result into one failure category."""
    if result.get("reward", 0) == 1:
        return "success"

    reason = result.get("failure_reason", "") or ""

    # Explicit annotation failures
    if reason == "invalid_task_annotation" or "invalid_task_annotation" in reason:
        return "invalid_task_annotation"

    # Runtime reasons
    if "max_turns" in reason:
        return "max_turns_exceeded"
    if "tool_error" in reason:
        return "tool_error"
    if "invalid_tool" in reason:
        return "invalid_tool_call"
    if "parser" in reason or "parse" in reason:
        return "parser_failure"

    # Reward-component analysis
    action_ok = result.get("action_reward", 1) == 1
    output_ok = result.get("output_reward", 1) == 1

    if not action_ok and not output_ok:
        return "wrong_database_state_and_missing_output"
    if not action_ok:
        return "wrong_database_state"
    if not output_ok:
        return "missing_required_output"

    # Generic non-zero failure_reason but rewards look ok
    if result.get("invalid_tool_calls", 0) > 0:
        return "invalid_tool_call"

    if reason and reason not in ("", "None"):
        return "unknown_failure"

    return "unknown_failure"


def analyze_failures(results_by_task: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trials = [t for trials in results_by_task.values() for t in trials]
    failed = [t for t in all_trials if t.get("reward", 0) == 0]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in failed:
        group = classify_failure(trial)
        groups[group].append(trial)

    total = len(all_trials)
    return {
        "total_trials": total,
        "total_failures": len(failed),
        "failure_rate": len(failed) / total if total > 0 else 0.0,
        "groups": {
            k: {"count": len(v), "task_ids": list({t.get("task_id", "?") for t in v})}
            for k, v in groups.items()
        },
    }
