"""Tests for calibration ranking logic."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from taufreebench.providers.calibration import load_best_free_model


def _mock_episode(reward: int, turns: int = 5, tool_calls: int = 3, invalid: int = 0, latency: float = 1.0):
    m = MagicMock()
    m.reward = reward
    m.turns = turns
    m.tool_calls = tool_calls
    m.invalid_tool_calls = invalid
    m.latency_seconds = latency
    m.model_dump.return_value = {
        "reward": reward,
        "turns": turns,
        "tool_calls": tool_calls,
        "invalid_tool_calls": invalid,
        "latency_seconds": latency,
        "failure_reason": None,
    }
    return m


def test_calibration_ranking_prefers_higher_pass1():
    """Model with higher pass^1 should rank first."""
    results = [
        {"provider": "ollama", "model": "model_a", "local": True, "pass_1": 0.9, "invalid_tool_call_rate": 0.0, "mean_latency_seconds": 2.0, "successes": 3, "trials": 3},
        {"provider": "ollama", "model": "model_b", "local": True, "pass_1": 0.3, "invalid_tool_call_rate": 0.0, "mean_latency_seconds": 1.0, "successes": 1, "trials": 3},
    ]
    results.sort(key=lambda r: (-r["pass_1"], r["invalid_tool_call_rate"], r["mean_latency_seconds"] or float("inf"), 0 if r["local"] else 1))
    assert results[0]["model"] == "model_a"


def test_calibration_ranking_prefers_lower_invalid_rate_when_tied():
    results = [
        {"provider": "ollama", "model": "a", "local": True, "pass_1": 1.0, "invalid_tool_call_rate": 0.2, "mean_latency_seconds": 1.0, "successes": 3, "trials": 3},
        {"provider": "ollama", "model": "b", "local": True, "pass_1": 1.0, "invalid_tool_call_rate": 0.0, "mean_latency_seconds": 2.0, "successes": 3, "trials": 3},
    ]
    results.sort(key=lambda r: (-r["pass_1"], r["invalid_tool_call_rate"], r["mean_latency_seconds"] or float("inf"), 0 if r["local"] else 1))
    assert results[0]["model"] == "b"


def test_calibration_ranking_prefers_local_when_tied():
    results = [
        {"provider": "gemini", "model": "gemini-flash", "local": False, "pass_1": 1.0, "invalid_tool_call_rate": 0.0, "mean_latency_seconds": 1.0, "successes": 3, "trials": 3},
        {"provider": "ollama", "model": "qwen3:8b", "local": True, "pass_1": 1.0, "invalid_tool_call_rate": 0.0, "mean_latency_seconds": 1.0, "successes": 3, "trials": 3},
    ]
    results.sort(key=lambda r: (-r["pass_1"], r["invalid_tool_call_rate"], r["mean_latency_seconds"] or float("inf"), 0 if r["local"] else 1))
    assert results[0]["model"] == "qwen3:8b"


def test_load_best_free_model_returns_none_if_not_calibrated(tmp_path, monkeypatch):
    """Should return None if calibration hasn't been run."""
    import taufreebench.providers.calibration as cal
    monkeypatch.setattr(cal, "RUNS_DIR", tmp_path / "calibration")
    result = load_best_free_model()
    assert result is None


def test_load_best_free_model_returns_saved_model(tmp_path, monkeypatch):
    import json
    import taufreebench.providers.calibration as cal
    cal_dir = tmp_path / "calibration"
    cal_dir.mkdir(parents=True)
    monkeypatch.setattr(cal, "RUNS_DIR", cal_dir)
    best = {"provider": "ollama", "model": "qwen3:8b"}
    (cal_dir / "best_free_model.json").write_text(json.dumps(best))
    result = load_best_free_model()
    assert result == best
