"""Render a benchmark run to JSON + Markdown report files."""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from taufreebench.core.diff import compact_diff_summary
from taufreebench.runners.analyze_failures import classify_failure

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


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


def _determine_validity(agent: str, user_simulator: str) -> tuple[str, str]:
    """Return (mode_key, validity_banner_text)."""
    is_llm_agent = agent not in ("rule",)
    is_llm_user = user_simulator not in ("scripted",)

    if not is_llm_agent and not is_llm_user:
        return (
            "deterministic_sanity_check",
            "VALIDITY: Deterministic sanity check. "
            "Not comparable to τ-bench paper results because this run uses a rule-based agent "
            "and scripted user. Do NOT compare these scores to the paper's GPT-4o results.",
        )
    if is_llm_agent and not is_llm_user:
        return (
            "partial_llm_benchmark",
            "VALIDITY: Partial LLM benchmark. "
            "Tests LLM agent tool-use and policy-following, but the user is scripted, "
            "so interaction is not fully paper-style. "
            "Scores are not directly comparable to the τ-bench paper.",
        )
    if is_llm_agent and is_llm_user:
        return (
            "mini_paper_style",
            "VALIDITY: Mini paper-style benchmark. "
            "Closest mode in this repo to the original τ-bench interaction loop. "
            "However, this is a custom/smaller dataset and is NOT the original τ-bench. "
            "Scores are internal benchmark scores only.",
        )
    return (
        "unknown",
        "VALIDITY: Configuration not clearly categorized.",
    )


def write_report(
    domain: str,
    agent: str,
    agent_model: str | None,
    user_simulator: str,
    trials: int,
    k_values: list[int],
    results_by_task: dict[str, list[dict[str, Any]]],
    metrics: dict[str, Any],
    tasks_by_id: dict[str, Any],
    user_model: str | None = None,
) -> Path:
    """Write episodes.json, metrics.json, and report.md to runs/<timestamp>/.

    Returns the path to report.md.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "runs" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    git_hash = _git_commit_hash()
    dataset_hash = _dataset_hash(domain)
    validity_mode, validity_banner = _determine_validity(agent, user_simulator)

    # Attach failure_class to each episode and enrich metrics
    for task_id, trials_list in results_by_task.items():
        for ep in trials_list:
            ep["failure_class"] = classify_failure(ep)

    # Add run metadata to metrics
    metrics["run_metadata"] = {
        "git_commit": git_hash,
        "dataset_hash": dataset_hash,
        "domain": domain,
        "task_count": len(results_by_task),
        "trials": trials,
        "k_values": k_values,
        "agent": agent,
        "agent_model": agent_model,
        "user_simulator": user_simulator,
        "user_model": user_model,
        "validity_mode": validity_mode,
        "timestamp": timestamp,
    }

    # Slim down trajectories before saving (full DBs are huge)
    slim_results: dict[str, list[dict[str, Any]]] = {}
    for task_id, trials_list in results_by_task.items():
        slim_results[task_id] = [_slim_episode(ep) for ep in trials_list]

    (out_dir / "episodes.json").write_text(json.dumps(slim_results, indent=2, default=str))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    md = _build_markdown(
        domain=domain,
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
    return report_path


def _slim_episode(ep: dict[str, Any]) -> dict[str, Any]:
    """Drop large DB blobs but keep trajectory and diff summary."""
    slim = {k: v for k, v in ep.items() if k not in ("final_db", "expected_db")}
    if "db_diff" in ep:
        slim["db_diff_summary"] = compact_diff_summary(ep["db_diff"])
    return slim


def _build_markdown(
    *,
    domain: str,
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

    lines.append(f"# Benchmark Report — {timestamp}")
    lines.append("")

    # --- Validity Banner (prominent) ---
    lines.append(f"> **{validity_banner}**")
    lines.append("")
    lines.append(
        "> This project is an educational, clean-room, mini τ-bench-style benchmark. "
        "It is not the original τ-bench and its scores are not directly comparable to the paper."
    )
    lines.append("")

    # --- Run Metadata ---
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Generated | {now} |")
    lines.append(f"| Git commit | `{git_hash}` |")
    lines.append(f"| Dataset hash | `{dataset_hash}` |")
    lines.append(f"| Domain | `{domain}` |")
    lines.append(f"| Task count | {len(results_by_task)} |")
    lines.append(f"| Trials per task | {trials} |")
    lines.append(f"| k values | {k_values} |")
    lines.append(f"| Agent | `{agent}`" + (f" / model `{agent_model}`" if agent_model else " |"))
    lines.append(f"| User simulator | `{user_simulator}`" + (f" / model `{user_model}`" if user_model else " |"))
    lines.append(f"| Validity mode | `{validity_mode}` |")
    lines.append("")

    # --- Aggregate Metrics ---
    lines.append("## Aggregate Metrics")
    lines.append("")
    for kv in k_values:
        lines.append(f"- **pass^{kv}**: {metrics.get(f'pass_hat_{kv}', 0):.3f}")
    for kv in k_values:
        lines.append(f"- **pass@{kv}**: {metrics.get(f'pass_at_{kv}', 0):.3f}")
    lines.append(f"- Avg turns: {metrics.get('avg_turns', 0):.2f}")
    lines.append(f"- Avg tool calls: {metrics.get('avg_tool_calls', 0):.2f}")
    lines.append(f"- Invalid tool call rate: {metrics.get('invalid_tool_call_rate', 0):.3f}")
    lines.append(f"- Max-turn failure rate: {metrics.get('max_turn_failure_rate', 0):.3f}")
    lines.append(f"- Tool-error rate: {metrics.get('tool_error_rate', 0):.3f}")
    if metrics.get("mean_latency_seconds") is not None:
        lines.append(f"- Mean latency: {metrics.get('mean_latency_seconds', 0):.2f}s")
    lines.append("")

    # --- Failure Breakdown ---
    failure_counter: dict[str, int] = {}
    for trials_list in results_by_task.values():
        for ep in trials_list:
            if ep.get("reward", 0) == 1:
                continue
            fc = ep.get("failure_class") or classify_failure(ep)
            failure_counter[fc] = failure_counter.get(fc, 0) + 1

    if failure_counter:
        lines.append("## Failure Breakdown")
        lines.append("")
        lines.append("| failure_class | count |")
        lines.append("|---|---|")
        for reason, cnt in sorted(failure_counter.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {cnt} |")
        lines.append("")

    # --- Per-Task Table ---
    lines.append("## Per-Task Results")
    lines.append("")
    header_cols = ["task_id", "tags", "successes/trials", "pass^1", "avg_turns", "failure_class", "diff_summary"]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cols)) + "|")

    per_task = metrics.get("per_task", [])
    per_task_by_id = {row["task_id"]: row for row in per_task}

    for task_id in results_by_task:
        trial_list = results_by_task[task_id]
        n = len(trial_list)
        c = sum(1 for t in trial_list if t.get("reward", 0) == 1)
        row = per_task_by_id.get(task_id, {})
        pass1 = row.get("pass_hat_1", 0.0)
        turns = sum(t.get("turns", 0) for t in trial_list) / n if n else 0
        # Failure class from first failing trial
        fails = [t for t in trial_list if t.get("reward", 0) != 1]
        fc = classify_failure(fails[0]) if fails else "—"
        tags = ",".join(tasks_by_id.get(task_id).tags) if tasks_by_id.get(task_id) else ""
        # Compact diff summary from first failing trial
        diff_str = "—"
        if fails:
            diff = fails[0].get("db_diff", {})
            if diff:
                s = compact_diff_summary(diff)
                parts = []
                if s.get("mismatched_values"):
                    parts.append(f"{s['mismatched_values']} mismatches")
                if s.get("missing_keys"):
                    parts.append(f"{s['missing_keys']} missing")
                if s.get("extra_keys"):
                    parts.append(f"{s['extra_keys']} extra")
                diff_str = "; ".join(parts) if parts else "diff"
        lines.append(f"| {task_id} | {tags} | {c}/{n} | {pass1:.2f} | {turns:.1f} | {fc} | {diff_str} |")
    lines.append("")

    # --- Easiest / Hardest ---
    sorted_tasks = sorted(per_task, key=lambda r: (-r.get("pass_hat_1", 0), r["task_id"]))
    easiest = [r for r in sorted_tasks if r.get("pass_hat_1", 0) > 0][:5]
    hardest = sorted(per_task, key=lambda r: (r.get("pass_hat_1", 0), r["task_id"]))[:5]
    if easiest:
        lines.append("## Top 5 Easiest Tasks")
        lines.append("")
        for r in easiest:
            lines.append(f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} ({r['successes']}/{r['n']})")
        lines.append("")
    if hardest:
        lines.append("## Top 5 Hardest Tasks")
        lines.append("")
        for r in hardest:
            lines.append(f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} ({r['successes']}/{r['n']})")
        lines.append("")

    # --- Trajectory Examples ---
    success_examples = _pick_examples(results_by_task, want_success=True, limit=3)
    fail_examples = _pick_examples(results_by_task, want_success=False, limit=3)

    if success_examples:
        lines.append("## Example Successful Trajectories")
        lines.append("")
        for ex in success_examples:
            _emit_trajectory_block(lines, ex, success=True)

    if fail_examples:
        lines.append("## Example Failed Trajectories")
        lines.append("")
        for ex in fail_examples:
            _emit_trajectory_block(lines, ex, success=False)

    # --- Paper-Comparability Section ---
    lines.append("## Paper-Comparability")
    lines.append("")
    lines.append("| Criterion | This Run |")
    lines.append("|---|---|")
    is_llm_agent = agent not in ("rule",)
    is_llm_user = user_simulator not in ("scripted",)
    lines.append(f"| LLM agent used | {'yes' if is_llm_agent else '**no** (rule-based)'} |")
    lines.append(f"| LLM user used | {'yes' if is_llm_user else '**no** (scripted)'} |")
    lines.append(f"| Strict DB-state evaluator | yes |")
    lines.append(f"| No LLM judge | yes |")
    lines.append(f"| Custom/mini dataset | yes (not original τ-bench) |")
    lines.append(f"| Task count | {len(results_by_task)} (original τ-retail: 115) |")
    lines.append(f"| Trials | {trials} |")
    lines.append(f"| pass^k implemented | yes |")
    lines.append(f"| pass@k implemented | yes |")
    lines.append("")

    if validity_mode == "deterministic_sanity_check":
        verdict = "❌ NOT paper-comparable. Rule-based agent + scripted user = deterministic sanity check only."
    elif validity_mode == "partial_llm_benchmark":
        verdict = "⚠️ PARTIALLY comparable. LLM agent tested, but scripted user differs from paper's LLM user."
    elif validity_mode == "mini_paper_style":
        verdict = "🟡 CLOSEST to paper-style in this repo. Still custom/smaller dataset — not original τ-bench."
    else:
        verdict = "❓ Comparability unclear."

    lines.append(f"**Verdict**: {verdict}")
    lines.append("")
    lines.append(
        "_Original τ-bench paper (Yao et al. 2024) used GPT-4o and Claude-3.5 on the full τ-retail (115 tasks) "
        "and τ-airline (128 tasks) datasets with LLM-simulated users. "
        "This repo uses a custom 25-task mini dataset and is NOT a reproduction of the paper._"
    )
    lines.append("")

    return "\n".join(lines)


def _pick_examples(
    results_by_task: dict[str, list[dict[str, Any]]],
    *,
    want_success: bool,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for task_id, trials_list in results_by_task.items():
        for ep in trials_list:
            success = ep.get("reward", 0) == 1
            if success == want_success:
                out.append(ep)
                break
        if len(out) >= limit:
            break
    return out


def _emit_trajectory_block(lines: list[str], ep: dict[str, Any], success: bool) -> None:
    task_id = ep.get("task_id", "?")
    fc = ep.get("failure_class") or (classify_failure(ep) if not success else "success")
    lines.append(f"### `{task_id}` — {'✅' if success else '❌'} reward={ep.get('reward')} failure_class={fc}")
    lines.append("")
    if not success and ep.get("db_diff"):
        s = compact_diff_summary(ep["db_diff"])
        lines.append(f"**DB diff summary**: {s.get('mismatched_values', 0)} mismatches, "
                     f"{s.get('missing_keys', 0)} missing keys, "
                     f"{s.get('extra_keys', 0)} extra keys")
        if s.get("first_changed_paths"):
            lines.append(f"First changed paths: `{', '.join(s['first_changed_paths'][:5])}`")
        lines.append("")
        lines.append("<details><summary>Full DB diff (click to expand)</summary>")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(ep["db_diff"], indent=2)[:2000])
        lines.append("```")
        lines.append("</details>")
        lines.append("")
    lines.append("Trajectory (truncated):")
    lines.append("")
    lines.append("```")
    for step in ep.get("trajectory", [])[:24]:
        role = step.get("role")
        content = step.get("content")
        if role == "user":
            txt = content.get("content", "") if isinstance(content, dict) else str(content)
            lines.append(f"USER : {txt[:160]}")
        elif role == "agent":
            if isinstance(content, dict) and content.get("name"):
                lines.append(f"TOOL→ {content.get('name')}({json.dumps(content.get('arguments', {}))[:100]})")
            else:
                txt = content.get("content", "") if isinstance(content, dict) else str(content)
                lines.append(f"AGENT: {txt[:160]}")
        elif role == "tool":
            result = content.get("result", "") if isinstance(content, dict) else content
            lines.append(f"RESLT: {str(result)[:160]}")
    lines.append("```")
    lines.append("")
