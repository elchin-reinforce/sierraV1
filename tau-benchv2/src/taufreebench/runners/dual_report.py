"""Render a dual-control benchmark run to JSON + Markdown report files.

Writes ``episodes.json``, ``metrics.json``, ``report.md`` and ``audit.md`` to
``runs/<timestamp>/``. Mirrors the style of `taufreebench.runners.report` but
adapted to the τ²-bench-style dual-control schema (assertions + dual tool
counters + mode banner).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        ).decode().strip()
    except Exception:
        return "unknown"


def _dataset_hash(domain: str) -> str:
    data_dir = PROJECT_ROOT / "data" / domain
    h = hashlib.sha256()
    for f in sorted(data_dir.glob("*.json")):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def _determine_dual_validity(
    mode: str, agent: str, user_simulator: str
) -> tuple[str, str]:
    """Return (validity_mode_key, validity_banner_text)."""
    is_llm_agent = agent not in ("rule",)
    is_llm_user = user_simulator not in ("scripted",) and mode != "no_user"

    if mode == "no_user":
        return (
            "dual_no_user",
            "VALIDITY: Sierra V2 dual-control benchmark, no-user mode. "
            "Agent handles an internal ticket alone with access to BOTH agent and user "
            "tools. This is an upper-bound oracle-ish check, NOT comparable to the "
            "τ²-bench paper (which always uses an LLM user).",
        )
    if mode == "oracle_plan":
        return (
            "dual_oracle_plan",
            "VALIDITY: Sierra V2 dual-control benchmark, oracle-plan mode. "
            "Agent receives the ground-truth high-level plan up front. Useful for "
            "ablations, NOT a paper-comparable score.",
        )

    if not is_llm_agent and not is_llm_user:
        return (
            "dual_sanity_check",
            "VALIDITY: Sierra V2 dual-control deterministic sanity check. "
            "Rule-based agent + scripted user. Not comparable to τ²-bench paper.",
        )
    if is_llm_agent and not is_llm_user:
        return (
            "dual_partial_llm",
            "VALIDITY: Sierra V2 dual-control partial LLM benchmark. "
            "LLM agent + scripted user; user does not behave like the paper's LLM "
            "user. Scores are not directly comparable to τ²-bench paper.",
        )
    if is_llm_agent and is_llm_user:
        return (
            "dual_mini_paper_style",
            "VALIDITY: Sierra V2 dual-control mini τ²-bench-style benchmark. "
            "Closest mode in this repo to the τ²-bench paper interaction loop "
            "(LLM agent + LLM user, both with tools). Still custom/smaller — NOT "
            "the original τ²-bench. Scores are internal-benchmark scores only.",
        )
    return ("dual_unknown", "VALIDITY: Configuration not clearly categorized.")


# ---------------------------------------------------------------------------
# Metrics aggregation (dual-flavoured)
# ---------------------------------------------------------------------------

def _safe_comb(n: int, k: int) -> int:
    from math import comb
    if n < 0 or k < 0 or k > n:
        return 0
    return comb(n, k)


def _pass_hat_k(c: int, n: int, k: int) -> float:
    if n < k or k <= 0:
        return 0.0
    denom = _safe_comb(n, k)
    if denom == 0:
        return 0.0
    return _safe_comb(c, k) / denom


def _pass_at_k(c: int, n: int, k: int) -> float:
    if n < k or k <= 0:
        return 0.0
    failures = n - c
    denom = _safe_comb(n, k)
    if denom == 0:
        return 0.0
    if failures < k:
        return 1.0
    return 1.0 - _safe_comb(failures, k) / denom


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def compute_dual_metrics(
    results_by_task: dict[str, list[dict[str, Any]]],
    k_values: list[int],
) -> dict[str, Any]:
    per_task: list[dict[str, Any]] = []
    for task_id, trials in results_by_task.items():
        n = len(trials)
        c = sum(1 for t in trials if t.get("reward", 0) == 1)
        row: dict[str, Any] = {"task_id": task_id, "n": n, "successes": c}
        for k in k_values:
            row[f"pass_hat_{k}"] = _pass_hat_k(c, n, k)
            row[f"pass_at_{k}"] = _pass_at_k(c, n, k)
        per_task.append(row)

    aggregated: dict[str, Any] = {}
    for k in k_values:
        aggregated[f"pass_hat_{k}"] = _mean([r[f"pass_hat_{k}"] for r in per_task])
        aggregated[f"pass_at_{k}"] = _mean([r[f"pass_at_{k}"] for r in per_task])

    all_trials = [t for trials in results_by_task.values() for t in trials]
    if all_trials:
        total = len(all_trials)
        aggregated["avg_turns"] = _mean([t.get("turns", 0) for t in all_trials])
        aggregated["avg_agent_tool_calls"] = _mean(
            [t.get("agent_tool_calls", 0) for t in all_trials]
        )
        aggregated["avg_user_tool_calls"] = _mean(
            [t.get("user_tool_calls", 0) for t in all_trials]
        )

        total_agent_tools = sum(t.get("agent_tool_calls", 0) for t in all_trials)
        total_user_tools = sum(t.get("user_tool_calls", 0) for t in all_trials)
        invalid_agent = sum(t.get("invalid_agent_tool_calls", 0) for t in all_trials)
        invalid_user = sum(t.get("invalid_user_tool_calls", 0) for t in all_trials)
        err_agent = sum(t.get("agent_tool_errors", 0) for t in all_trials)
        err_user = sum(t.get("user_tool_errors", 0) for t in all_trials)
        aggregated["invalid_agent_tool_rate"] = (
            invalid_agent / total_agent_tools if total_agent_tools else 0.0
        )
        aggregated["invalid_user_tool_rate"] = (
            invalid_user / total_user_tools if total_user_tools else 0.0
        )
        aggregated["agent_tool_error_rate"] = (
            err_agent / total_agent_tools if total_agent_tools else 0.0
        )
        aggregated["user_tool_error_rate"] = (
            err_user / total_user_tools if total_user_tools else 0.0
        )

        aggregated["max_turn_failure_rate"] = sum(
            1 for t in all_trials
            if (t.get("failure_reason") or "") in (
                "max_turns_exceeded", "max_agent_actions_exceeded"
            )
        ) / total

        aggregated["assertion_failure_rate"] = sum(
            1 for t in all_trials if t.get("assertion_reward", 0) == 0
        ) / total
        aggregated["output_failure_rate"] = sum(
            1 for t in all_trials if t.get("output_reward", 0) == 0
        ) / total

        latencies = [t.get("latency_seconds") for t in all_trials if t.get("latency_seconds") is not None]
        aggregated["mean_latency_seconds"] = _mean(latencies) if latencies else None

    aggregated["per_task"] = per_task
    return aggregated


# ---------------------------------------------------------------------------
# Episode slimming
# ---------------------------------------------------------------------------

def _slim_episode(ep: dict[str, Any]) -> dict[str, Any]:
    """Drop massive DB blobs from saved episode but keep trajectory + counters."""
    drop = {"final_agent_db", "final_user_db", "expected_agent_db", "expected_user_db"}
    return {k: v for k, v in ep.items() if k not in drop}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_dual_report(
    domain: str,
    mode: str,
    agent: str,
    agent_model: str | None,
    user_simulator: str,
    user_model: str | None,
    trials: int,
    k_values: list[int],
    results_by_task: dict[str, list[dict[str, Any]]],
    metrics: dict[str, Any],
    tasks_by_id: dict[str, Any],
    out_dir: Path | None = None,
) -> Path:
    """Write episodes.json, metrics.json, report.md, audit.md.

    Returns the path to `report.md`.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if out_dir is None:
        out_dir = PROJECT_ROOT / "runs" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    git_hash = _git_commit_hash()
    dataset_hash = _dataset_hash(domain)
    validity_mode, validity_banner = _determine_dual_validity(mode, agent, user_simulator)

    metrics["run_metadata"] = {
        "git_commit": git_hash,
        "dataset_hash": dataset_hash,
        "domain": domain,
        "task_count": len(results_by_task),
        "trials": trials,
        "k_values": k_values,
        "mode": mode,
        "agent": agent,
        "agent_model": agent_model,
        "user_simulator": user_simulator,
        "user_model": user_model,
        "validity_mode": validity_mode,
        "timestamp": timestamp,
    }

    slim_results = {
        task_id: [_slim_episode(ep) for ep in trials_list]
        for task_id, trials_list in results_by_task.items()
    }
    (out_dir / "episodes.json").write_text(json.dumps(slim_results, indent=2, default=str))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    md = _build_markdown(
        domain=domain,
        mode=mode,
        agent=agent,
        agent_model=agent_model,
        user_simulator=user_simulator,
        user_model=user_model,
        trials=trials,
        k_values=k_values,
        results_by_task=results_by_task,
        metrics=metrics,
        tasks_by_id=tasks_by_id,
        timestamp=timestamp,
        git_hash=git_hash,
        dataset_hash=dataset_hash,
        validity_banner=validity_banner,
        validity_mode=validity_mode,
    )
    report_path = out_dir / "report.md"
    report_path.write_text(md)

    audit = _build_audit(
        domain=domain,
        mode=mode,
        agent=agent,
        user_simulator=user_simulator,
        trials=trials,
        k_values=k_values,
        task_count=len(results_by_task),
        git_hash=git_hash,
        dataset_hash=dataset_hash,
        validity_mode=validity_mode,
    )
    (out_dir / "audit.md").write_text(audit)

    return report_path


# ---------------------------------------------------------------------------
# Markdown construction
# ---------------------------------------------------------------------------

def _issue_counts(tasks_by_id: dict[str, Any]) -> Counter:
    return Counter(getattr(t, "issue_type", "unknown") for t in tasks_by_id.values())


def _persona_counts(tasks_by_id: dict[str, Any]) -> Counter:
    return Counter(getattr(t, "persona_id", "none") or "none" for t in tasks_by_id.values())


def _subtask_count_breakdown(tasks_by_id: dict[str, Any]) -> Counter:
    out: Counter = Counter()
    for t in tasks_by_id.values():
        diff = getattr(t, "difficulty", {}) or {}
        out[diff.get("n_subtasks", "?")] += 1
    return out


def _group_pass_hat_1(
    results_by_task: dict[str, list[dict[str, Any]]],
    tasks_by_id: dict[str, Any],
    grouper,
) -> dict[Any, dict[str, float]]:
    """Return ``{group_key: {n_tasks, pass_hat_1, pass_at_1}}``."""
    grouped: dict[Any, list[tuple[int, int]]] = {}
    for task_id, trials_list in results_by_task.items():
        task = tasks_by_id.get(task_id)
        if task is None:
            continue
        key = grouper(task)
        n = len(trials_list)
        c = sum(1 for t in trials_list if t.get("reward", 0) == 1)
        grouped.setdefault(key, []).append((c, n))

    out: dict[Any, dict[str, float]] = {}
    for key, pairs in grouped.items():
        passhat = _mean([_pass_hat_k(c, n, 1) for c, n in pairs])
        passat = _mean([_pass_at_k(c, n, 1) for c, n in pairs])
        out[key] = {"n_tasks": len(pairs), "pass_hat_1": passhat, "pass_at_1": passat}
    return out


def _build_markdown(
    *,
    domain: str,
    mode: str,
    agent: str,
    agent_model: str | None,
    user_simulator: str,
    user_model: str | None,
    trials: int,
    k_values: list[int],
    results_by_task: dict[str, list[dict[str, Any]]],
    metrics: dict[str, Any],
    tasks_by_id: dict[str, Any],
    timestamp: str,
    git_hash: str,
    dataset_hash: str,
    validity_banner: str,
    validity_mode: str,
) -> str:
    lines: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")

    lines.append(f"# Sierra V2 Dual-Control Benchmark Report — {timestamp}")
    lines.append("")
    lines.append(
        "> **Sierra V2 Dual-Control Benchmark Report — mini τ²-bench-style, NOT "
        "original τ²-bench, scores not comparable to paper.**"
    )
    lines.append("")
    lines.append(f"> {validity_banner}")
    lines.append("")

    # --- Run metadata ---------------------------------------------------
    issue_counts = _issue_counts(tasks_by_id)
    persona_counts = _persona_counts(tasks_by_id)

    lines.append("## Run Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Generated | {now} |")
    lines.append(f"| Git commit | `{git_hash}` |")
    lines.append(f"| Dataset hash | `{dataset_hash}` |")
    lines.append(f"| Domain | `{domain}` |")
    lines.append(f"| Mode | `{mode}` |")
    lines.append(f"| Agent | `{agent}`" + (f" / `{agent_model}`" if agent_model else "") + " |")
    lines.append(
        f"| User simulator | `{user_simulator}`"
        + (f" / `{user_model}`" if user_model else "")
        + " |"
    )
    lines.append(f"| Trials per task | {trials} |")
    lines.append(f"| k values | {k_values} |")
    lines.append(f"| Total tasks | {len(results_by_task)} |")
    lines.append(
        f"| Issue types | "
        + ", ".join(f"{k}={v}" for k, v in sorted(issue_counts.items()))
        + " |"
    )
    lines.append(
        f"| Personas | "
        + ", ".join(f"{k}={v}" for k, v in sorted(persona_counts.items()))
        + " |"
    )
    lines.append(f"| Validity mode | `{validity_mode}` |")
    lines.append("")

    # --- Aggregate metrics ----------------------------------------------
    lines.append("## Aggregate Metrics")
    lines.append("")
    for kv in k_values:
        lines.append(f"- **pass^{kv}**: {metrics.get(f'pass_hat_{kv}', 0):.3f}")
    for kv in k_values:
        lines.append(f"- **pass@{kv}**: {metrics.get(f'pass_at_{kv}', 0):.3f}")
    lines.append(f"- Avg turns: {metrics.get('avg_turns', 0):.2f}")
    lines.append(f"- Avg agent tool calls: {metrics.get('avg_agent_tool_calls', 0):.2f}")
    lines.append(f"- Avg user tool calls: {metrics.get('avg_user_tool_calls', 0):.2f}")
    lines.append(f"- Invalid agent tool rate: {metrics.get('invalid_agent_tool_rate', 0):.3f}")
    lines.append(f"- Invalid user tool rate: {metrics.get('invalid_user_tool_rate', 0):.3f}")
    lines.append(f"- Agent tool-error rate: {metrics.get('agent_tool_error_rate', 0):.3f}")
    lines.append(f"- User tool-error rate: {metrics.get('user_tool_error_rate', 0):.3f}")
    lines.append(f"- Max-turn failure rate: {metrics.get('max_turn_failure_rate', 0):.3f}")
    lines.append(f"- Assertion failure rate: {metrics.get('assertion_failure_rate', 0):.3f}")
    lines.append(f"- Output failure rate: {metrics.get('output_failure_rate', 0):.3f}")
    if metrics.get("mean_latency_seconds") is not None:
        lines.append(f"- Mean latency: {metrics['mean_latency_seconds']:.2f}s")
    lines.append("")

    # --- Breakdown by issue_type ----------------------------------------
    lines.append("## Breakdown by Issue Type")
    lines.append("")
    by_issue = _group_pass_hat_1(
        results_by_task, tasks_by_id, lambda t: getattr(t, "issue_type", "unknown")
    )
    lines.append("| issue_type | tasks | pass^1 | pass@1 |")
    lines.append("|---|---|---|---|")
    for key in sorted(by_issue):
        row = by_issue[key]
        lines.append(
            f"| {key} | {row['n_tasks']} | {row['pass_hat_1']:.3f} | {row['pass_at_1']:.3f} |"
        )
    lines.append("")

    # --- Breakdown by persona -------------------------------------------
    lines.append("## Breakdown by Persona")
    lines.append("")
    by_persona = _group_pass_hat_1(
        results_by_task, tasks_by_id,
        lambda t: getattr(t, "persona_id", None) or "none",
    )
    lines.append("| persona | tasks | pass^1 | pass@1 |")
    lines.append("|---|---|---|---|")
    for key in sorted(by_persona):
        row = by_persona[key]
        lines.append(
            f"| {key} | {row['n_tasks']} | {row['pass_hat_1']:.3f} | {row['pass_at_1']:.3f} |"
        )
    lines.append("")

    # --- Breakdown by subtask count -------------------------------------
    lines.append("## Breakdown by Subtask Count")
    lines.append("")
    by_n = _group_pass_hat_1(
        results_by_task, tasks_by_id,
        lambda t: (getattr(t, "difficulty", {}) or {}).get("n_subtasks", "?"),
    )
    lines.append("| n_subtasks | tasks | pass^1 |")
    lines.append("|---|---|---|")
    for key in sorted(by_n, key=lambda x: (x is None, x)):
        row = by_n[key]
        lines.append(f"| {key} | {row['n_tasks']} | {row['pass_hat_1']:.3f} |")
    lines.append("")

    # --- Failure breakdown ----------------------------------------------
    failure_counter: Counter = Counter()
    for trials_list in results_by_task.values():
        for ep in trials_list:
            if ep.get("reward", 0) == 1:
                continue
            failure_counter[ep.get("failure_class") or "unknown_failure"] += 1
    if failure_counter:
        lines.append("## Failure Breakdown")
        lines.append("")
        lines.append("| failure_class | count |")
        lines.append("|---|---|")
        for fc, cnt in failure_counter.most_common():
            lines.append(f"| {fc} | {cnt} |")
        lines.append("")

    # --- Easiest / hardest ----------------------------------------------
    per_task = metrics.get("per_task", [])
    easiest = sorted(per_task, key=lambda r: (-r.get("pass_hat_1", 0), r["task_id"]))
    easiest = [r for r in easiest if r.get("pass_hat_1", 0) > 0][:5]
    hardest = sorted(per_task, key=lambda r: (r.get("pass_hat_1", 0), r["task_id"]))[:5]
    if easiest:
        lines.append("## Top 5 Easiest Tasks")
        lines.append("")
        for r in easiest:
            lines.append(
                f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} "
                f"({r['successes']}/{r['n']})"
            )
        lines.append("")
    if hardest:
        lines.append("## Top 5 Hardest Tasks")
        lines.append("")
        for r in hardest:
            lines.append(
                f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} "
                f"({r['successes']}/{r['n']})"
            )
        lines.append("")

    # --- Example trajectories -------------------------------------------
    success_examples = _pick_examples(results_by_task, want_success=True, limit=3)
    fail_examples = _pick_examples(results_by_task, want_success=False, limit=3)

    if success_examples:
        lines.append("## Example Successful Trajectories")
        lines.append("")
        for ex in success_examples:
            _emit_dual_trajectory_block(lines, ex, success=True)
    if fail_examples:
        lines.append("## Example Failed Trajectories")
        lines.append("")
        for ex in fail_examples:
            _emit_dual_trajectory_block(lines, ex, success=False)

    # --- Paper comparability --------------------------------------------
    lines.append("## Paper-Comparability (τ²-bench)")
    lines.append("")
    lines.append("| Criterion | This Run | τ²-bench Paper |")
    lines.append("|---|---|---|")
    is_llm_agent = agent not in ("rule",)
    is_llm_user = user_simulator not in ("scripted",) and mode != "no_user"
    lines.append(
        f"| Dual-control (agent + user with tools) | "
        f"{'yes' if mode != 'no_user' else 'no (no-user mode)'} | yes |"
    )
    lines.append(f"| LLM agent | {'yes' if is_llm_agent else '**no** (rule-based)'} | yes (GPT-4o / Claude-3.5) |")
    lines.append(
        f"| LLM user with tools | "
        f"{'yes' if is_llm_user else ('n/a (no-user mode)' if mode == 'no_user' else '**no** (scripted)')} | yes |"
    )
    lines.append(f"| Assertion-based evaluation | yes | yes |")
    lines.append(f"| No LLM judge | yes | yes |")
    lines.append(f"| Dataset | custom 60-task mini (this repo) | original τ²-bench (telecom: ~114) |")
    lines.append(f"| Task count | {len(results_by_task)} | ~114 (telecom) |")
    lines.append(f"| Trials | {trials} | typically 4-5 |")
    lines.append(f"| pass^k / pass@k | yes | pass^k |")
    lines.append("")

    verdict = _verdict_for_mode(validity_mode)
    lines.append(f"**Verdict**: {verdict}")
    lines.append("")
    lines.append(
        "_Original τ²-bench (Sierra/Yao 2025) uses a dual-control setup with an LLM "
        "agent, an LLM user simulator, and a much larger curated task set. This repo "
        "is a clean-room educational mini reimplementation; scores are NOT directly "
        "comparable to the paper._"
    )
    lines.append("")

    return "\n".join(lines)


def _verdict_for_mode(validity_mode: str) -> str:
    if validity_mode == "dual_sanity_check":
        return (
            "NOT paper-comparable. Rule-based agent + scripted user = deterministic "
            "sanity check only."
        )
    if validity_mode == "dual_partial_llm":
        return (
            "PARTIALLY comparable. LLM agent tested, but scripted user differs from "
            "paper's LLM user."
        )
    if validity_mode == "dual_mini_paper_style":
        return (
            "CLOSEST to paper-style in this repo (LLM agent + LLM user, both with "
            "tools). Still custom/smaller dataset — not original τ²-bench."
        )
    if validity_mode == "dual_no_user":
        return (
            "Oracle-ish upper bound only (no-user mode). Not paper-comparable; the "
            "paper always uses an LLM user."
        )
    if validity_mode == "dual_oracle_plan":
        return "Ablation only (oracle-plan mode). Not paper-comparable."
    return "Comparability unclear."


def _pick_examples(
    results_by_task: dict[str, list[dict[str, Any]]],
    *,
    want_success: bool,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for trials_list in results_by_task.values():
        for ep in trials_list:
            success = ep.get("reward", 0) == 1
            if success == want_success:
                out.append(ep)
                break
        if len(out) >= limit:
            break
    return out


def _emit_dual_trajectory_block(lines: list[str], ep: dict[str, Any], success: bool) -> None:
    task_id = ep.get("task_id", "?")
    fc = ep.get("failure_class") or ("success" if success else "unknown_failure")
    mark = "PASS" if success else "FAIL"
    lines.append(
        f"### `{task_id}` — {mark} reward={ep.get('reward')} failure_class={fc} "
        f"mode={ep.get('mode', '?')}"
    )
    lines.append("")
    assertion_results = ep.get("assertion_results") or []
    if assertion_results:
        failing = [a for a in assertion_results if not a.get("passed")]
        passing = [a for a in assertion_results if a.get("passed")]
        lines.append(
            f"Assertions: {len(passing)}/{len(assertion_results)} passing."
        )
        if failing:
            lines.append("")
            lines.append("Failing assertions:")
            for a in failing[:5]:
                lines.append(f"- `{a.get('name')}` — {a.get('detail', '')}")
        lines.append("")
    lines.append("Trajectory (truncated):")
    lines.append("")
    lines.append("```")
    for step in (ep.get("trajectory") or [])[:24]:
        role = step.get("role")
        content = step.get("content")
        if role == "user":
            txt = content.get("content", "") if isinstance(content, dict) else str(content)
            lines.append(f"USER  : {txt[:160]}")
        elif role == "agent":
            txt = content.get("content", "") if isinstance(content, dict) else str(content)
            lines.append(f"AGENT : {txt[:160]}")
        elif role == "agent_tool":
            if isinstance(content, dict) and content.get("name"):
                args = json.dumps(content.get("args", content.get("arguments", {})), default=str)
                lines.append(f"A→TOOL: {content.get('name')}({args[:120]})")
                if "result" in content:
                    lines.append(f"  ↳   : {str(content.get('result'))[:120]}")
        elif role == "user_tool":
            if isinstance(content, dict) and content.get("name"):
                args = json.dumps(content.get("args", content.get("arguments", {})), default=str)
                lines.append(f"U→TOOL: {content.get('name')}({args[:120]})")
                if "result" in content:
                    lines.append(f"  ↳   : {str(content.get('result'))[:120]}")
        elif role == "environment":
            txt = content.get("content", "") if isinstance(content, dict) else str(content)
            lines.append(f"ENV   : {str(txt)[:160]}")
    lines.append("```")
    lines.append("")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def _build_audit(
    *,
    domain: str,
    mode: str,
    agent: str,
    user_simulator: str,
    trials: int,
    k_values: list[int],
    task_count: int,
    git_hash: str,
    dataset_hash: str,
    validity_mode: str,
) -> str:
    is_llm_agent = agent not in ("rule",)
    is_llm_user = user_simulator not in ("scripted",) and mode != "no_user"

    lines: list[str] = []
    lines.append(f"# τ²-bench Validity Audit — {domain} / mode={mode}")
    lines.append("")
    lines.append(
        "This is a clean-room educational mini τ²-bench-style benchmark. "
        "It is **not** the original τ²-bench and its scores are not directly "
        "comparable to the paper."
    )
    lines.append("")

    # Section A: environment loop
    lines.append("## A. Environment Loop")
    lines.append("")
    lines.append("| Check | Status | Notes |")
    lines.append("|---|---|---|")
    lines.append("| Agent sees policy, conversation, agent-tool results | PASS | by design |")
    lines.append("| Agent does NOT see user-side tool calls/results | PASS | trajectory `visible_to_*` flags |")
    lines.append(
        "| User has its own tool set and DB view | "
        + ("PASS" if mode != "no_user" else "n/a (no-user mode)")
        + " | dual-control |"
    )
    lines.append("| Agent and user mutate JSON DBs via tools only | PASS | by design |")
    lines.append(
        "| Mode used | "
        + f"`{mode}`"
        + " | one of {default, no_user, oracle_plan} |"
    )
    lines.append("")

    # Section B: evaluation
    lines.append("## B. Evaluation")
    lines.append("")
    lines.append("| Check | Status | Notes |")
    lines.append("|---|---|---|")
    lines.append("| Outcome judged by post-state assertions | PASS | `run_assertions` over final dbs |")
    lines.append("| Required-output substring check | PASS | case-insensitive substring match |")
    lines.append("| No LLM judge used | PASS | deterministic |")
    lines.append(f"| pass^k implemented | PASS | k={k_values} |")
    lines.append(f"| pass@k implemented | PASS | k={k_values} |")
    lines.append(
        "| Failure classification | PASS | success / assertion_failed / "
        "max_turns_exceeded / invalid_*_tool_call / *_tool_error / "
        "missing_required_output / incomplete_troubleshooting / ... |"
    )
    lines.append("")

    # Section C: comparability
    lines.append("## C. Comparability to τ²-bench Paper")
    lines.append("")
    lines.append("| Criterion | This Run | τ²-bench Paper |")
    lines.append("|---|---|---|")
    lines.append(
        f"| LLM agent | {'yes' if is_llm_agent else 'no (rule-based)'} | yes |"
    )
    lines.append(
        f"| LLM user with tools | "
        f"{'yes' if is_llm_user else ('n/a (no-user mode)' if mode == 'no_user' else 'no (scripted)')} "
        f"| yes |"
    )
    lines.append(f"| Telecom task count | {task_count} | ~114 |")
    lines.append(f"| Trials | {trials} | typically 4-5 |")
    lines.append(f"| Dataset | custom mini (this repo) | original τ²-bench |")
    lines.append(f"| Git commit | `{git_hash}` | — |")
    lines.append(f"| Dataset hash | `{dataset_hash}` | — |")
    lines.append(f"| Validity mode | `{validity_mode}` | — |")
    lines.append("")
    lines.append(f"**Verdict**: {_verdict_for_mode(validity_mode)}")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "compute_dual_metrics",
    "write_dual_report",
]
