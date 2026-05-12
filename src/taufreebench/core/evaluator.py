"""Episode evaluator: replay expected actions and compare DB states."""
from __future__ import annotations
import copy
from typing import Any

from .types import Task, EpisodeResult, TrajectoryStep
from .tool import ToolDefinition
from .diff import compute_db_diff, diffs_are_empty


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
    expected_db = _replay_expected_actions(task, initial_db, domain_tools)
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
        provider=provider,
        model=model,
        turns=turns,
        tool_calls=tool_calls,
        invalid_tool_calls=invalid_tool_calls,
        latency_seconds=latency_seconds,
    )


def _replay_expected_actions(
    task: Task,
    initial_db: dict[str, Any],
    domain_tools: dict[str, ToolDefinition],
) -> dict[str, Any]:
    db = copy.deepcopy(initial_db)
    for action in task.expected_actions:
        tool = domain_tools.get(action.name)
        if tool is None:
            continue
        try:
            tool(db, **action.arguments)
        except Exception:
            pass
    return db


def _check_required_outputs(required_outputs: list[str], agent_messages: list[str]) -> int:
    if not required_outputs:
        return 1
    combined = " ".join(agent_messages).lower()
    for substring in required_outputs:
        if substring.lower() not in combined:
            return 0
    return 1
