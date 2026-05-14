"""Tests for report validity banners and metadata."""
from __future__ import annotations
from taufreebench.runners.report import _determine_validity, _build_markdown


def test_rule_scripted_is_deterministic_sanity_check():
    mode, banner = _determine_validity("rule", "scripted")
    assert mode == "deterministic_sanity_check"
    assert "not comparable" in banner.lower() or "not comparable" in banner.lower()
    assert "rule-based" in banner.lower()


def test_llm_scripted_is_partial_llm_benchmark():
    mode, banner = _determine_validity("ollama", "scripted")
    assert mode == "partial_llm_benchmark"
    assert "partial" in banner.lower()
    assert "scripted" in banner.lower()


def test_llm_llm_is_mini_paper_style():
    mode, banner = _determine_validity("ollama", "ollama")
    assert mode == "mini_paper_style"
    assert "mini" in banner.lower() or "closest" in banner.lower()


def _make_mock_report(agent, user_sim):
    metrics = {
        "pass_hat_1": 0.9,
        "pass_at_1": 0.9,
        "avg_turns": 5.0,
        "avg_tool_calls": 3.0,
        "invalid_tool_call_rate": 0.0,
        "max_turn_failure_rate": 0.0,
        "tool_error_rate": 0.0,
        "per_task": [],
    }
    results_by_task = {}
    tasks_by_id = {}
    from taufreebench.runners.report import _determine_validity
    _, validity_banner = _determine_validity(agent, user_sim)
    validity_mode, _ = _determine_validity(agent, user_sim)

    return _build_markdown(
        domain="retail",
        agent=agent,
        agent_model=None,
        user_simulator=user_sim,
        user_model=None,
        trials=1,
        k_values=[1],
        results_by_task=results_by_task,
        metrics=metrics,
        tasks_by_id=tasks_by_id,
        timestamp="20260512_000000",
        git_hash="abc1234",
        dataset_hash="deadbeef0000",
        validity_banner=validity_banner,
        validity_mode=validity_mode,
    )


def test_rule_scripted_report_contains_not_comparable():
    md = _make_mock_report("rule", "scripted")
    assert "not comparable" in md.lower() or "deterministic sanity check" in md.lower()


def test_llm_scripted_report_contains_partial():
    md = _make_mock_report("ollama", "scripted")
    assert "partial" in md.lower()


def test_llm_llm_report_contains_mini_paper():
    md = _make_mock_report("ollama", "ollama")
    assert "mini" in md.lower() or "closest" in md.lower()


def test_report_contains_disclaimer():
    md = _make_mock_report("rule", "scripted")
    assert "not the original τ-bench" in md or "not the original" in md.lower()
