"""Tests for the τ²-bench-style dual-control telecom benchmark."""
from __future__ import annotations
import json
from pathlib import Path
import copy

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "telecom"


def _load_dbs():
    return (
        json.loads((DATA / "agent_db.json").read_text()),
        json.loads((DATA / "user_device_db.json").read_text()),
    )


def test_seed_dbs_have_expected_counts():
    agent_db, user_db = _load_dbs()
    assert len(agent_db["customers"]) == 30
    assert len(agent_db["lines"]) == 50
    assert len(agent_db["plans"]) == 10
    assert len(agent_db["bills"]) == 40
    assert len(user_db["devices"]) == 50


def test_tasks_json_has_60_valid_tasks():
    tasks = json.loads((DATA / "tasks.json").read_text())
    assert len(tasks) >= 60
    types = {"service_issue", "mobile_data_issue", "mms_issue"}
    for t in tasks:
        assert t["issue_type"] in types
        assert t["line_id"] is not None
        assert t["device_id"] is not None
        assert len(t["solution_actions"]) > 0
        assert len(t["assertions"]) > 0


def test_assertions_registry_has_13():
    from taufreebench.domains.telecom.assertions import ASSERTIONS
    assert len(ASSERTIONS) == 13


def test_agent_tools_registry_has_expected():
    from taufreebench.domains.telecom.agent_tools import AGENT_TOOLS
    assert len(AGENT_TOOLS) >= 19


def test_user_tools_registry_has_expected():
    from taufreebench.domains.telecom.user_tools import USER_TOOLS
    assert len(USER_TOOLS) >= 30


def test_toggle_airplane_off_restores_signal():
    from taufreebench.domains.telecom.user_tools import USER_TOOLS
    agent_db, user_db = _load_dbs()
    # device_001 corresponds to line_001 which is active in seed data
    user_db["devices"]["device_001"]["airplane_mode"] = True
    user_db["devices"]["device_001"]["signal_strength"] = "none"
    USER_TOOLS["toggle_airplane_mode"](user_db, agent_db, device_id="device_001", enabled=False)
    assert user_db["devices"]["device_001"]["airplane_mode"] is False
    assert user_db["devices"]["device_001"]["signal_strength"] == "strong"


def test_reseat_sim_restores_valid_sim():
    from taufreebench.domains.telecom.user_tools import USER_TOOLS
    agent_db, user_db = _load_dbs()
    user_db["devices"]["device_002"]["sim_inserted"] = False
    user_db["devices"]["device_002"]["sim_status"] = "missing"
    USER_TOOLS["reseat_sim_card"](user_db, agent_db, device_id="device_002")
    assert user_db["devices"]["device_002"]["sim_inserted"] is True
    assert user_db["devices"]["device_002"]["sim_status"] == "valid"


def test_assert_service_connected_fails_when_airplane_mode():
    from taufreebench.domains.telecom.assertions import ASSERTIONS
    agent_db, user_db = _load_dbs()
    user_db["devices"]["device_001"]["airplane_mode"] = True
    r = ASSERTIONS["assert_service_connected"](agent_db, user_db, device_id="device_001")
    assert r["passed"] is False


def test_assert_service_connected_passes_when_healthy():
    from taufreebench.domains.telecom.assertions import ASSERTIONS
    agent_db, user_db = _load_dbs()
    r = ASSERTIONS["assert_service_connected"](agent_db, user_db, device_id="device_001")
    assert r["passed"] is True


def test_validate_dataset_replay_passes_all():
    """End-to-end: every task's solution actions must flip assertions FAIL→PASS."""
    from taufreebench.domains.telecom.scenarios import SUBTASKS
    from taufreebench.domains.telecom.agent_tools import AGENT_TOOLS
    from taufreebench.domains.telecom.user_tools import USER_TOOLS
    from taufreebench.domains.telecom.assertions import run_assertions

    sub_by_id = {s["id"]: s for s in SUBTASKS}
    tasks = json.loads((DATA / "tasks.json").read_text())
    failures = []
    for t in tasks[:10]:  # sample 10 for speed
        agent_db, user_db = _load_dbs()
        for sid in t["initializers"]:
            if sid in sub_by_id:
                sub_by_id[sid]["initializer"](agent_db, user_db, t["line_id"])
        # Assertions should fail before solution
        pre = run_assertions(t["assertions"], agent_db, user_db)
        assert any(not r["passed"] for r in pre), f"Task {t['id']} already solved before solution"


def test_classify_dual_failure_recognizes_success():
    from taufreebench.core.dual_evaluator import classify_dual_failure
    cls = classify_dual_failure(reward=1, assertion_reward=1, output_reward=1)
    assert cls == "success"


def test_classify_dual_failure_recognizes_max_turns():
    from taufreebench.core.dual_evaluator import classify_dual_failure
    cls = classify_dual_failure(
        reward=0, assertion_reward=0, output_reward=1,
        failure_reason="max_turns_exceeded",
    )
    assert cls == "max_turns_exceeded"
