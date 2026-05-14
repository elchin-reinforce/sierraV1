"""Run one dual-control (τ²-bench-style) episode for the telecom domain."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taufreebench.core.dual_environment import DualControlEnvironment
from taufreebench.core.types import DualEpisodeResult, TelecomTask


def _project_root() -> Path:
    """Return tau-benchv2 project root.

    File layout: src/taufreebench/runners/run_dual_episode.py
    parents:    [runners, taufreebench, src, project_root]
    """
    return Path(__file__).resolve().parents[3]


def load_telecom_dbs() -> tuple[dict[str, Any], dict[str, Any]]:
    root = _project_root()
    agent_db = json.loads((root / "data" / "telecom" / "agent_db.json").read_text())
    user_db = json.loads((root / "data" / "telecom" / "user_device_db.json").read_text())
    return agent_db, user_db


def load_telecom_policy() -> str:
    root = _project_root()
    return (root / "data" / "telecom" / "policy.md").read_text()


def load_telecom_tasks() -> list[TelecomTask]:
    root = _project_root()
    raw = json.loads((root / "data" / "telecom" / "tasks.json").read_text())
    return [TelecomTask(**t) for t in raw]


def apply_initializers(
    task: TelecomTask, agent_db: dict[str, Any], user_db: dict[str, Any]
) -> None:
    """Apply each subtask initializer referenced by the task in order.

    Mutates `agent_db` / `user_db` in place. The initializers are looked up by
    id in `scenarios.SUBTASKS` (they are Python callables that cannot be
    serialized into the tasks.json file).
    """
    from taufreebench.domains.telecom.scenarios import SUBTASKS

    sub_by_id = {s["id"]: s for s in SUBTASKS}
    for sub_id in task.initializers:
        sub = sub_by_id.get(sub_id)
        if sub is None:
            continue
        initializer = sub.get("initializer")
        if initializer is None or task.line_id is None:
            continue
        initializer(agent_db, user_db, task.line_id)


def _make_dual_agent(agent_type: str, agent_model: str | None = None):
    if agent_type == "rule":
        from taufreebench.agents.rule_based_telecom_agent import RuleBasedTelecomAgent
        return RuleBasedTelecomAgent()
    if agent_type == "ollama":
        from taufreebench.agents.ollama_dual_tool_agent import OllamaDualToolAgent
        return OllamaDualToolAgent(model=agent_model)
    if agent_type == "openai":
        from taufreebench.agents.openai_dual_tool_agent import OpenAIDualToolAgent
        return OpenAIDualToolAgent(model=agent_model)
    if agent_type == "anthropic":
        from taufreebench.agents.anthropic_dual_tool_agent import AnthropicDualToolAgent
        return AnthropicDualToolAgent(model=agent_model)
    raise ValueError(f"Unknown dual agent type: {agent_type}")


def _make_dual_user(user_type: str, task_id: str, user_model: str | None = None):
    if user_type == "scripted":
        from taufreebench.users.scripted_dual_user import ScriptedDualUser
        return ScriptedDualUser(task_id=task_id)
    if user_type == "ollama":
        from taufreebench.users.ollama_dual_user import OllamaDualUser
        return OllamaDualUser(model=user_model)
    if user_type == "openai":
        from taufreebench.users.openai_dual_user import OpenAIDualUser
        return OpenAIDualUser(model=user_model)
    if user_type == "anthropic":
        from taufreebench.users.anthropic_dual_user import AnthropicDualUser
        return AnthropicDualUser(model=user_model)
    raise ValueError(f"Unknown dual user type: {user_type}")


def run_dual_episode_for_task(
    task_id: str,
    mode: str = "default",
    agent_type: str = "rule",
    agent_model: str | None = None,
    user_type: str = "scripted",
    user_model: str | None = None,
) -> DualEpisodeResult:
    """Run a single dual-control episode for the given telecom task id."""
    agent_db, user_db = load_telecom_dbs()
    policy = load_telecom_policy()
    tasks = load_telecom_tasks()
    task_map = {t.id: t for t in tasks}
    if task_id not in task_map:
        raise ValueError(
            f"Task '{task_id}' not found. Available: {len(task_map)} tasks "
            f"(first: {next(iter(task_map), '?')})"
        )
    task = task_map[task_id]

    # Inject the issue described by each subtask into a fresh dbs snapshot.
    apply_initializers(task, agent_db, user_db)

    from taufreebench.domains.telecom.agent_tools import AGENT_TOOLS
    from taufreebench.domains.telecom.user_tools import USER_TOOLS

    agent = _make_dual_agent(agent_type, agent_model)
    user = _make_dual_user(user_type, task_id, user_model) if mode != "no_user" else None

    env = DualControlEnvironment(
        domain_name="telecom",
        agent_db=agent_db,
        user_db=user_db,
        agent_tools=AGENT_TOOLS,
        user_tools=USER_TOOLS,
        policy=policy,
        task=task,
        user_simulator=user,
        agent=agent,
        mode=mode,  # type: ignore[arg-type]
    )
    return env.run_episode()
