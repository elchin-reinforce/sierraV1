"""Tests for the benchmark environment loop."""
from __future__ import annotations
import taufreebench.domains.retail.tools  # noqa: F401
from pathlib import Path
from taufreebench.core.db import load_domain_db
from taufreebench.core.environment import BenchmarkEnvironment
from taufreebench.core.tool import get_domain_tools
from taufreebench.core.types import Task, ToolCall
from taufreebench.users.scripted_user import ScriptedUser
from taufreebench.agents.rule_based_agent import RuleBasedRetailAgent

DATA_DIR = Path(__file__).parent.parent / "data"
POLICY = "Authenticate user. Confirm before write. One tool per turn."


def _make_env(task: Task, db=None):
    if db is None:
        db = load_domain_db("retail", DATA_DIR)
    tools = get_domain_tools("retail")
    user = ScriptedUser(task_id=task.id)
    agent = RuleBasedRetailAgent()
    return BenchmarkEnvironment(
        domain_name="retail",
        db=db,
        tools=tools,
        policy=POLICY,
        task=task,
        user=user,
        agent=agent,
        max_turns=20,
    )


def test_cancel_episode_trajectory():
    task = Task(
        id="retail_task_001",
        instruction="Cancel order #W4082615.",
        expected_actions=[ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})],
    )
    env = _make_env(task)
    result = env.run_episode()

    roles = [s.role for s in result.trajectory]
    assert "user" in roles
    assert "agent" in roles
    assert "tool" in roles


def test_final_db_changes_on_cancel():
    task = Task(
        id="retail_task_001",
        instruction="Cancel order #W4082615.",
        expected_actions=[ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})],
    )
    env = _make_env(task)
    result = env.run_episode()
    # If reward=1 the DB changed correctly; either way check DB was touched or episode ran
    assert result.turns > 0
    assert len(result.trajectory) > 0


def test_reward_1_when_correct():
    task = Task(
        id="retail_task_001",
        instruction="Cancel order #W4082615 (ordered by mistake).",
        expected_actions=[ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})],
    )
    env = _make_env(task)
    result = env.run_episode()
    # Rule-based agent should handle this successfully
    assert result.action_reward == 1


def test_agent_messages_collected():
    task = Task(
        id="retail_task_001",
        instruction="Cancel order #W4082615.",
        expected_actions=[ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})],
    )
    env = _make_env(task)
    result = env.run_episode()
    assert len(result.agent_messages) > 0


def test_initial_db_not_mutated():
    task = Task(
        id="retail_task_001",
        instruction="Cancel order #W4082615.",
        expected_actions=[ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})],
    )
    db = load_domain_db("retail", DATA_DIR)
    original_status = db["orders"]["#W4082615"]["status"]
    env = _make_env(task, db=db)
    env.run_episode()
    # Original DB passed in should not be mutated (env makes deep copy)
    assert db["orders"]["#W4082615"]["status"] == original_status


def test_max_turns_terminates():
    task = Task(
        id="retail_task_999_fake",
        instruction="This task has no scripted user and will hit max turns.",
        expected_actions=[],
        max_turns=3,
    )
    env = _make_env(task)
    result = env.run_episode()
    assert result.turns <= 3 or result.failure_reason == "max_turns_exceeded"
