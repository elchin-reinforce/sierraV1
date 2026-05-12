"""Tests for the episode evaluator."""
from __future__ import annotations
import copy
import pytest
import taufreebench.domains.retail.tools  # noqa: F401
from pathlib import Path
from taufreebench.core.db import load_domain_db
from taufreebench.core.evaluator import evaluate_episode
from taufreebench.core.tool import get_domain_tools
from taufreebench.core.types import Task, ToolCall

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def db():
    return load_domain_db("retail", DATA_DIR)


@pytest.fixture
def tools():
    return get_domain_tools("retail")


def test_expected_actions_produce_expected_db(db, tools):
    task = Task(
        id="t1",
        instruction="",
        expected_actions=[
            ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})
        ],
    )
    initial = copy.deepcopy(db)
    # Simulate agent doing the right thing
    final_db = copy.deepcopy(db)
    tools["cancel_pending_order"](final_db, order_id="#W4082615", reason="ordered by mistake")

    result = evaluate_episode(
        task=task,
        initial_db=initial,
        final_db=final_db,
        agent_messages=["Your order has been cancelled."],
        domain_tools=tools,
        trajectory=[],
    )
    assert result.action_reward == 1
    assert result.reward == 1


def test_wrong_final_db_gives_action_reward_0(db, tools):
    task = Task(
        id="t2",
        instruction="",
        expected_actions=[
            ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})
        ],
    )
    initial = copy.deepcopy(db)
    final_db = copy.deepcopy(db)  # Agent did nothing

    result = evaluate_episode(
        task=task,
        initial_db=initial,
        final_db=final_db,
        agent_messages=["Sorry, I cannot help."],
        domain_tools=tools,
        trajectory=[],
    )
    assert result.action_reward == 0
    assert result.reward == 0
    assert result.db_diff  # There should be diffs


def test_missing_required_output_gives_output_reward_0(db, tools):
    task = Task(
        id="t3",
        instruction="",
        expected_actions=[],
        required_outputs=["processed"],
    )
    initial = copy.deepcopy(db)
    final_db = copy.deepcopy(db)

    result = evaluate_episode(
        task=task,
        initial_db=initial,
        final_db=final_db,
        agent_messages=["I cannot help with that order."],
        domain_tools=tools,
        trajectory=[],
    )
    assert result.output_reward == 0
    assert result.reward == 0


def test_required_output_present_gives_output_reward_1(db, tools):
    task = Task(
        id="t4",
        instruction="",
        expected_actions=[],
        required_outputs=["processed"],
    )
    initial = copy.deepcopy(db)
    final_db = copy.deepcopy(db)

    result = evaluate_episode(
        task=task,
        initial_db=initial,
        final_db=final_db,
        agent_messages=["The order is processed and cannot be cancelled."],
        domain_tools=tools,
        trajectory=[],
    )
    assert result.output_reward == 1


def test_no_required_outputs_gives_output_reward_1(db, tools):
    task = Task(id="t5", instruction="", expected_actions=[], required_outputs=[])
    initial = copy.deepcopy(db)
    result = evaluate_episode(task=task, initial_db=initial, final_db=copy.deepcopy(db), agent_messages=[], domain_tools=tools, trajectory=[])
    assert result.output_reward == 1


def test_reward_is_product(db, tools):
    task = Task(
        id="t6",
        instruction="",
        expected_actions=[
            ToolCall(name="cancel_pending_order", arguments={"order_id": "#W4082615", "reason": "ordered by mistake"})
        ],
        required_outputs=["cancelled"],
    )
    initial = copy.deepcopy(db)
    final_db = copy.deepcopy(db)
    tools["cancel_pending_order"](final_db, order_id="#W4082615", reason="ordered by mistake")

    result = evaluate_episode(
        task=task,
        initial_db=initial,
        final_db=final_db,
        agent_messages=["Your order has been cancelled."],
        domain_tools=tools,
        trajectory=[],
    )
    assert result.action_reward == 1
    assert result.output_reward == 1
    assert result.reward == 1
