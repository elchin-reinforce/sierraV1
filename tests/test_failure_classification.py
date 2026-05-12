"""Tests for failure classification."""
from __future__ import annotations
from taufreebench.runners.analyze_failures import classify_failure


def _ep(reward=0, action_reward=1, output_reward=1, failure_reason=None, invalid_tool_calls=0):
    return {
        "reward": reward,
        "action_reward": action_reward,
        "output_reward": output_reward,
        "failure_reason": failure_reason,
        "invalid_tool_calls": invalid_tool_calls,
    }


def test_success():
    assert classify_failure(_ep(reward=1)) == "success"


def test_invalid_task_annotation():
    assert classify_failure(_ep(failure_reason="invalid_task_annotation")) == "invalid_task_annotation"


def test_max_turns_exceeded():
    assert classify_failure(_ep(failure_reason="max_turns_exceeded")) == "max_turns_exceeded"


def test_tool_error():
    assert classify_failure(_ep(failure_reason="tool_error: something went wrong")) == "tool_error"


def test_wrong_database_state():
    assert classify_failure(_ep(action_reward=0, output_reward=1)) == "wrong_database_state"


def test_missing_required_output():
    assert classify_failure(_ep(action_reward=1, output_reward=0)) == "missing_required_output"


def test_wrong_database_state_and_missing_output():
    assert classify_failure(_ep(action_reward=0, output_reward=0)) == "wrong_database_state_and_missing_output"


def test_invalid_tool_call():
    assert classify_failure(_ep(failure_reason="invalid_tool_call_detected", action_reward=1, output_reward=1)) == "invalid_tool_call"


def test_parser_failure():
    assert classify_failure(_ep(failure_reason="parser_failed: json parse error")) == "parser_failure"


def test_unknown_failure_when_no_signal():
    # reward=0 but no failure signal
    result = classify_failure({"reward": 0, "action_reward": 1, "output_reward": 1, "failure_reason": "some_other_error"})
    assert result == "unknown_failure"
