"""Episode evaluator: replay expected actions and compare DB states."""
from __future__ import annotations
import copy
from typing import Any

from .types import Task, EpisodeResult, TrajectoryStep
from .tool import ToolDefinition
from .diff import compute_db_diff, diffs_are_empty


class DatasetValidationError(Exception):
    """Raised when a task's expected_actions cannot be replayed cleanly."""


def replay_expected_actions_strict(
    task: Task,
    initial_db: dict[str, Any],
    domain_tools: dict[str, ToolDefinition],
) -> dict[str, Any]:
    """Replay expected actions strictly; raise DatasetValidationError on any problem."""
    db = copy.deepcopy(initial_db)
    for action in task.expected_actions:
        tool = domain_tools.get(action.name)
        if tool is None:
            raise DatasetValidationError(
                f"Task {task.id}: expected action '{action.name}' references a missing tool"
            )
        try:
            result = tool(db, **action.arguments)
        except Exception as exc:
            raise DatasetValidationError(
                f"Task {task.id}: expected action '{action.name}' raised exception: {exc}"
            ) from exc
        if isinstance(result, dict) and "error" in result:
            raise DatasetValidationError(
                f"Task {task.id}: expected action '{action.name}' returned error: {result['error']}"
            )
        if isinstance(result, str) and result.startswith("Error:"):
            raise DatasetValidationError(
                f"Task {task.id}: expected action '{action.name}' returned error: {result}"
            )
    return db


def evaluate_episode(
    task: Task,
    initial_db: dict[str, Any],
    final_db: dict[str, Any],
    agent_messages: list[str],
    domain_tools: dict[str, ToolDefinition],
    trajectory: list[TrajectoryStep],
    provider: str | None = None,
    model: str | None = None,
    turns: int = 0,
    tool_calls: int = 0,
    invalid_tool_calls: int = 0,
    latency_seconds: float | None = None,
    failure_reason: str | None = None,
) -> EpisodeResult:
    debug_metadata: dict[str, Any] = {}
    annotation_error: str | None = None

    try:
        expected_db = replay_expected_actions_strict(task, initial_db, domain_tools)
    except DatasetValidationError as exc:
        annotation_error = str(exc)
        debug_metadata["annotation_error"] = annotation_error
        return EpisodeResult(
            task_id=task.id,
            reward=0,
            action_reward=0,
            output_reward=0,
            trajectory=trajectory,
            final_db=final_db,
            expected_db=copy.deepcopy(initial_db),
            db_diff={},
            agent_messages=agent_messages,
            failure_reason="invalid_task_annotation",
            failure_class="invalid_task_annotation",
            provider=provider,
            model=model,
            turns=turns,
            tool_calls=tool_calls,
            invalid_tool_calls=invalid_tool_calls,
            latency_seconds=latency_seconds,
            debug_metadata=debug_metadata,
        )

    db_diff = compute_db_diff(expected_db, final_db)
    action_reward = 1 if diffs_are_empty(db_diff) else 0
    output_reward = _check_required_outputs(task.required_outputs, agent_messages)
    reward = action_reward * output_reward

    return EpisodeResult(
        task_id=task.id,
        reward=reward,
        action_reward=action_reward,
        output_reward=output_reward,
        trajectory=trajectory,
        final_db=final_db,
        expected_db=expected_db,
        db_diff=db_diff,
        agent_messages=agent_messages,
        failure_reason=failure_reason,
        failure_class=None,
        provider=provider,
        model=model,
        turns=turns,
        tool_calls=tool_calls,
        invalid_tool_calls=invalid_tool_calls,
        latency_seconds=latency_seconds,
        debug_metadata=debug_metadata,
    )


def _check_required_outputs(required_outputs: list[str], agent_messages: list[str]) -> int:
    if not required_outputs:
        return 1
    combined = " ".join(agent_messages).lower()
    for substring in required_outputs:
        if substring.lower() not in combined:
            return 0
    return 1
