"""Dual-control episode evaluator (τ²-bench-style).

Given the artifacts produced by a dual-control episode (final agent_db,
final user_db, agent + user messages, trajectory, and counters), compute the
reward, output reward, failure classification and produce a
``DualEpisodeResult``.

Also provides ``replay_solution_actions`` which applies a task's
``solution_actions`` against initial dbs in order, raising
``DualValidationError`` if any tool is missing or returns an error.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from .types import (
    DualEpisodeResult,
    DualMode,
    DualTrajectoryStep,
    TelecomTask,
)
from ..domains.telecom.assertions import run_assertions


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------

class DualValidationError(Exception):
    """Raised when a task's solution_actions cannot be replayed cleanly."""


# ----------------------------------------------------------------------------
# Required output check
# ----------------------------------------------------------------------------

def _check_required_outputs(required_outputs: list[str], agent_messages: list[str]) -> int:
    """Return 1 iff every required substring appears (case-insensitive) in the
    concatenated agent messages, else 0. Empty list trivially passes.
    """
    if not required_outputs:
        return 1
    combined = " ".join(agent_messages).lower()
    for substring in required_outputs:
        if not substring:
            continue
        if substring.lower() not in combined:
            return 0
    return 1


# ----------------------------------------------------------------------------
# Failure classification
# ----------------------------------------------------------------------------

def classify_dual_failure(
    reward: int,
    assertion_reward: int,
    output_reward: int,
    failure_reason: str | None = None,
    invalid_agent_tool_calls: int = 0,
    invalid_user_tool_calls: int = 0,
    agent_tool_errors: int = 0,
    user_tool_errors: int = 0,
) -> str:
    """Map the episode signals onto one of the supported failure classes."""
    if reward == 1:
        return "success"

    if failure_reason in ("max_turns_exceeded", "max_agent_actions_exceeded"):
        return "max_turns_exceeded"

    if failure_reason == "user_transfer":
        # User-initiated transfer is only a "premature_transfer" failure when
        # assertions were not satisfied (i.e. issue not actually resolved).
        if assertion_reward == 0:
            return "premature_transfer"

    if failure_reason == "premature_user_stop":
        return "premature_user_stop"

    if failure_reason == "wrong_backend_action":
        return "wrong_backend_action"

    if failure_reason == "wrong_user_instruction":
        return "wrong_user_instruction"

    if failure_reason == "coordination_failure":
        return "coordination_failure"

    if invalid_agent_tool_calls > 0:
        return "invalid_agent_tool_call"
    if invalid_user_tool_calls > 0:
        return "invalid_user_tool_call"
    if agent_tool_errors > 0:
        return "agent_tool_error"
    if user_tool_errors > 0:
        return "user_tool_error"

    if assertion_reward == 0 and output_reward == 1:
        return "assertion_failed"
    if output_reward == 0 and assertion_reward == 1:
        return "missing_required_output"
    if assertion_reward == 0 and output_reward == 0:
        return "incomplete_troubleshooting"

    return "unknown_failure"


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------

def evaluate_dual_episode(
    task: TelecomTask,
    agent_db: dict[str, Any],
    user_db: dict[str, Any],
    agent_messages: list[str],
    user_messages: list[str],
    agent_tools: dict[str, Callable],
    user_tools: dict[str, Callable],
    trajectory: list[DualTrajectoryStep],
    mode: str = "default",
    failure_reason: str | None = None,
    turns: int = 0,
    agent_tool_calls: int = 0,
    user_tool_calls: int = 0,
    invalid_agent_tool_calls: int = 0,
    invalid_user_tool_calls: int = 0,
    agent_tool_errors: int = 0,
    user_tool_errors: int = 0,
    latency_seconds: float | None = None,
    agent_provider: str | None = None,
    agent_model: str | None = None,
    user_provider: str | None = None,
    user_model: str | None = None,
) -> DualEpisodeResult:
    """Evaluate a completed dual-control episode and return a DualEpisodeResult.

    The episode's tool calls have already been applied to ``agent_db`` /
    ``user_db`` by the environment; we only judge the outcome.
    """
    # ----- Assertions -------------------------------------------------------
    assertion_results = run_assertions(task.assertions or [], agent_db, user_db)
    if assertion_results:
        assertion_reward = 1 if all(r.get("passed") for r in assertion_results) else 0
    else:
        # No assertions specified — vacuously true.
        assertion_reward = 1

    # ----- Required outputs -------------------------------------------------
    output_reward = _check_required_outputs(task.required_outputs or [], agent_messages)

    reward = int(assertion_reward * output_reward)

    failure_class = classify_dual_failure(
        reward=reward,
        assertion_reward=assertion_reward,
        output_reward=output_reward,
        failure_reason=failure_reason,
        invalid_agent_tool_calls=invalid_agent_tool_calls,
        invalid_user_tool_calls=invalid_user_tool_calls,
        agent_tool_errors=agent_tool_errors,
        user_tool_errors=user_tool_errors,
    )

    # Compact diff: MVP returns empty dict; downstream tooling can compute it.
    compact_diff: dict[str, Any] = {}

    mode_value: DualMode = mode if mode in ("default", "no_user", "oracle_plan") else "default"  # type: ignore[assignment]

    return DualEpisodeResult(
        task_id=task.id,
        reward=reward,
        assertion_reward=assertion_reward,
        output_reward=output_reward,
        action_match_reward=None,
        trajectory=trajectory,
        final_agent_db=agent_db,
        final_user_db=user_db,
        expected_agent_db=None,
        expected_user_db=None,
        assertion_results=assertion_results,
        db_diff={},
        compact_diff=compact_diff,
        agent_messages=agent_messages,
        user_messages=user_messages,
        failure_reason=failure_reason,
        failure_class=failure_class,
        agent_provider=agent_provider,
        agent_model=agent_model,
        user_provider=user_provider,
        user_model=user_model,
        turns=turns,
        agent_tool_calls=agent_tool_calls,
        user_tool_calls=user_tool_calls,
        invalid_agent_tool_calls=invalid_agent_tool_calls,
        invalid_user_tool_calls=invalid_user_tool_calls,
        agent_tool_errors=agent_tool_errors,
        user_tool_errors=user_tool_errors,
        latency_seconds=latency_seconds,
        mode=mode_value,
    )


# ----------------------------------------------------------------------------
# Solution-action replay (dataset validation helper)
# ----------------------------------------------------------------------------

def _looks_like_error(result: Any) -> tuple[bool, str]:
    """Best-effort check whether a tool return value indicates an error.

    Returns (is_error, detail).
    """
    if isinstance(result, dict):
        if "error" in result and result["error"]:
            return True, str(result["error"])
        # Some tools return {"status": "error", ...}.
        status = result.get("status")
        if isinstance(status, str) and status.lower() == "error":
            return True, str(result.get("message") or result)
    if isinstance(result, str) and result.startswith("Error:"):
        return True, result
    return False, ""


def replay_solution_actions(
    task: TelecomTask,
    agent_db: dict[str, Any],
    user_db: dict[str, Any],
    agent_tools: dict[str, Callable],
    user_tools: dict[str, Callable],
) -> dict[str, Any]:
    """Apply each solution action in order against deep-copies of the dbs.

    Returns ``{"agent_db": ..., "user_db": ...}`` with the post-replay state.
    Raises ``DualValidationError`` if any action references an unknown tool,
    raises an exception, or returns an error-shaped result.
    """
    out_agent = copy.deepcopy(agent_db)
    out_user = copy.deepcopy(user_db)

    for idx, action in enumerate(task.solution_actions or []):
        actor = getattr(action, "actor", None)
        name = getattr(action, "name", None)
        arguments = getattr(action, "arguments", {}) or {}

        if actor == "agent":
            registry = agent_tools
            actor_label = "agent"
        elif actor == "user":
            registry = user_tools
            actor_label = "user"
        else:
            raise DualValidationError(
                f"Task {task.id}: solution action #{idx} has invalid actor '{actor}'"
            )

        fn = registry.get(name) if name else None
        if fn is None:
            raise DualValidationError(
                f"Task {task.id}: solution action #{idx} '{actor_label}.{name}' "
                f"references a missing tool"
            )

        try:
            result = fn(out_agent, out_user, **arguments)
        except Exception as exc:  # noqa: BLE001 — surfacing the underlying error
            raise DualValidationError(
                f"Task {task.id}: solution action #{idx} '{actor_label}.{name}' "
                f"raised exception: {exc}"
            ) from exc

        is_err, detail = _looks_like_error(result)
        if is_err:
            raise DualValidationError(
                f"Task {task.id}: solution action #{idx} '{actor_label}.{name}' "
                f"returned error: {detail}"
            )

    return {"agent_db": out_agent, "user_db": out_user}


__all__ = [
    "DualValidationError",
    "classify_dual_failure",
    "evaluate_dual_episode",
    "replay_solution_actions",
]
