"""Tests for dataset validation and integrity."""
from __future__ import annotations
import pytest
from pathlib import Path
import taufreebench.domains.retail.tools  # noqa: F401
from taufreebench.runners.validate_dataset import validate_dataset
from taufreebench.core.evaluator import replay_expected_actions_strict, DatasetValidationError
from taufreebench.core.db import load_domain_db
from taufreebench.core.tool import get_domain_tools
from taufreebench.runners.run_episode import _load_tasks

DATA_DIR = Path(__file__).parent.parent / "data"


def test_all_retail_tasks_replay_cleanly():
    """Every retail task should pass strict replay (no DatasetValidationError)."""
    db = load_domain_db("retail", DATA_DIR)
    tools = get_domain_tools("retail")
    tasks = _load_tasks("retail", DATA_DIR)

    errors = []
    for task in tasks:
        try:
            replay_expected_actions_strict(task, db, tools)
        except DatasetValidationError as exc:
            errors.append(f"{task.id}: {exc}")

    assert errors == [], f"Tasks with invalid annotations:\n" + "\n".join(errors)


def test_required_outputs_are_strings():
    tasks = _load_tasks("retail", DATA_DIR)
    for task in tasks:
        for ro in task.required_outputs:
            assert isinstance(ro, str), f"Task {task.id}: required_output {ro!r} is not a string"


def test_expected_actions_reference_real_tools():
    tools = get_domain_tools("retail")
    tasks = _load_tasks("retail", DATA_DIR)
    for task in tasks:
        for action in task.expected_actions:
            assert action.name in tools, (
                f"Task {task.id}: expected_action '{action.name}' not in tool registry"
            )


def test_validate_dataset_all_ok():
    results = validate_dataset("retail", DATA_DIR)
    invalid = [r for r in results if r["status"] != "ok"]
    assert invalid == [], f"Invalid tasks: {[r['task_id'] for r in invalid]}"
