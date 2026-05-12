"""Tests for pass^k and pass@k metrics."""
from __future__ import annotations
import pytest
from taufreebench.core.metrics import pass_hat_k, pass_at_k, compute_metrics


def test_pass_hat_1_all_succeed():
    assert pass_hat_k(successes=3, trials=3, k=1) == pytest.approx(1.0)


def test_pass_hat_1_none_succeed():
    assert pass_hat_k(successes=0, trials=3, k=1) == pytest.approx(0.0)


def test_pass_hat_1_half():
    assert pass_hat_k(successes=1, trials=2, k=1) == pytest.approx(0.5)


def test_pass_hat_2_all_succeed():
    # C(3,2)/C(3,2) = 1
    assert pass_hat_k(successes=3, trials=3, k=2) == pytest.approx(1.0)


def test_pass_hat_2_one_of_three():
    # C(1,2)/C(3,2) = 0/3 = 0
    assert pass_hat_k(successes=1, trials=3, k=2) == pytest.approx(0.0)


def test_pass_hat_2_two_of_three():
    # C(2,2)/C(3,2) = 1/3
    assert pass_hat_k(successes=2, trials=3, k=2) == pytest.approx(1 / 3)


def test_pass_at_1_all_succeed():
    assert pass_at_k(successes=3, trials=3, k=1) == pytest.approx(1.0)


def test_pass_at_1_none_succeed():
    assert pass_at_k(successes=0, trials=3, k=1) == pytest.approx(0.0)


def test_pass_at_1_half():
    assert pass_at_k(successes=1, trials=2, k=1) == pytest.approx(0.5)


def test_pass_at_2_all_fail():
    # 1 - C(3,2)/C(3,2) = 0
    assert pass_at_k(successes=0, trials=3, k=2) == pytest.approx(0.0)


def test_pass_at_2_all_succeed():
    assert pass_at_k(successes=3, trials=3, k=2) == pytest.approx(1.0)


def test_pass_at_2_one_of_three():
    # failures=2, 1 - C(2,2)/C(3,2) = 1 - 1/3 = 2/3
    assert pass_at_k(successes=1, trials=3, k=2) == pytest.approx(2 / 3)


def test_pass_at_k_insufficient_trials():
    # Can't compute pass@k with fewer trials than k
    assert pass_at_k(successes=1, trials=1, k=2) == pytest.approx(0.0)


def test_compute_metrics_basic():
    results = {
        "task_a": [{"reward": 1, "turns": 5, "tool_calls": 3, "invalid_tool_calls": 0, "latency_seconds": 2.0}, {"reward": 0, "turns": 10, "tool_calls": 5, "invalid_tool_calls": 1, "latency_seconds": 4.0}],
        "task_b": [{"reward": 1, "turns": 3, "tool_calls": 2, "invalid_tool_calls": 0, "latency_seconds": 1.0}, {"reward": 1, "turns": 4, "tool_calls": 2, "invalid_tool_calls": 0, "latency_seconds": 1.5}],
    }
    m = compute_metrics(results, k_values=[1, 2])
    assert 0.0 <= m["pass_hat_1"] <= 1.0
    assert 0.0 <= m["pass_at_1"] <= 1.0
    assert m["avg_turns"] > 0
    assert m["avg_tool_calls"] > 0


def test_compute_metrics_all_succeed():
    results = {"t": [{"reward": 1, "turns": 3, "tool_calls": 2, "invalid_tool_calls": 0, "latency_seconds": None} for _ in range(3)]}
    m = compute_metrics(results, k_values=[1])
    assert m["pass_hat_1"] == pytest.approx(1.0)
    assert m["pass_at_1"] == pytest.approx(1.0)


def test_compute_metrics_none_succeed():
    results = {"t": [{"reward": 0, "turns": 3, "tool_calls": 2, "invalid_tool_calls": 0, "latency_seconds": None} for _ in range(3)]}
    m = compute_metrics(results, k_values=[1])
    assert m["pass_hat_1"] == pytest.approx(0.0)
    assert m["pass_at_1"] == pytest.approx(0.0)
