"""Render a benchmark run to JSON + Markdown report files."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


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
) -> Path:
    """Write episodes.json, metrics.json, and report.md to runs/<timestamp>/.

    Returns the path to report.md.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "runs" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # Slim down trajectories before saving raw episodes (full DBs are huge)
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
        trials=trials,
        k_values=k_values,
        results_by_task=results_by_task,
        metrics=metrics,
        tasks_by_id=tasks_by_id,
        timestamp=timestamp,
    )
    report_path = out_dir / "report.md"
    report_path.write_text(md)
    return report_path


def _slim_episode(ep: dict[str, Any]) -> dict[str, Any]:
    """Drop large DB blobs but keep trajectory for examples."""
    return {k: v for k, v in ep.items() if k not in ("final_db", "expected_db")}


def _build_markdown(
    *,
    domain: str,
    agent: str,
    agent_model: str | None,
    user_simulator: str,
    trials: int,
    k_values: list[int],
    results_by_task: dict[str, list[dict[str, Any]]],
    metrics: dict[str, Any],
    tasks_by_id: dict[str, Any],
    timestamp: str,
) -> str:
    lines: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")
    lines.append(f"# Benchmark Report — {timestamp}")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Domain: `{domain}`")
    lines.append(f"- Agent: `{agent}`" + (f" / model `{agent_model}`" if agent_model else ""))
    lines.append(f"- User simulator: `{user_simulator}`")
    lines.append(f"- Tasks: {len(results_by_task)}")
    lines.append(f"- Trials per task: {trials}")
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    for kv in k_values:
        lines.append(f"- **pass^{kv}**: {metrics.get(f'pass_hat_{kv}', 0):.3f}")
    for kv in k_values:
        lines.append(f"- **pass@{kv}**: {metrics.get(f'pass_at_{kv}', 0):.3f}")
    lines.append(f"- Avg turns: {metrics.get('avg_turns', 0):.2f}")
    lines.append(f"- Avg tool calls: {metrics.get('avg_tool_calls', 0):.2f}")
    lines.append(f"- Invalid tool call rate: {metrics.get('invalid_tool_call_rate', 0):.3f}")
    lines.append(f"- Max-turn failure rate: {metrics.get('max_turn_failure_rate', 0):.3f}")
    if metrics.get("mean_latency_seconds") is not None:
        lines.append(f"- Mean latency: {metrics.get('mean_latency_seconds', 0):.2f}s")
    lines.append("")

    # Failure breakdown
    failure_counter: dict[str, int] = {}
    for trials_list in results_by_task.values():
        for ep in trials_list:
            if ep.get("reward", 0) == 1:
                continue
            reason = ep.get("failure_reason")
            if not reason:
                reason = "incorrect_db_state" if ep.get("action_reward", 1) == 0 else "missing_required_output"
            failure_counter[reason] = failure_counter.get(reason, 0) + 1
    if failure_counter:
        lines.append("## Failure breakdown")
        lines.append("")
        lines.append("| reason | count |")
        lines.append("|---|---|")
        for reason, cnt in sorted(failure_counter.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {cnt} |")
        lines.append("")

    # Per-task table
    lines.append("## Per-task results")
    lines.append("")
    lines.append("| task_id | tags | successes/trials | pass^1 | avg turns | failure reason |")
    lines.append("|---|---|---|---|---|---|")
    per_task = metrics.get("per_task", [])
    per_task_by_id = {row["task_id"]: row for row in per_task}
    for task_id in results_by_task:
        trial_list = results_by_task[task_id]
        n = len(trial_list)
        c = sum(1 for t in trial_list if t.get("reward", 0) == 1)
        row = per_task_by_id.get(task_id, {})
        pass1 = row.get("pass_hat_1", 0.0)
        turns = sum(t.get("turns", 0) for t in trial_list) / n if n else 0
        fails = [t.get("failure_reason") for t in trial_list if t.get("reward", 0) != 1]
        fail_reason = next((f for f in fails if f), "—") if fails else "—"
        if fails and not fail_reason or fail_reason == "—":
            # Use synthetic categorisation for non-runtime failures
            if any(t.get("reward", 0) != 1 for t in trial_list):
                fail_reason = "db_mismatch_or_missing_output"
        tags = ",".join(tasks_by_id.get(task_id).tags) if tasks_by_id.get(task_id) else ""
        lines.append(f"| {task_id} | {tags} | {c}/{n} | {pass1:.2f} | {turns:.1f} | {fail_reason} |")
    lines.append("")

    # Easiest / hardest
    sorted_tasks = sorted(per_task, key=lambda r: (-r.get("pass_hat_1", 0), r["task_id"]))
    easiest = [r for r in sorted_tasks if r.get("pass_hat_1", 0) > 0][:5]
    hardest = sorted(per_task, key=lambda r: (r.get("pass_hat_1", 0), r["task_id"]))[:5]
    if easiest:
        lines.append("## Top 5 easiest tasks")
        lines.append("")
        for r in easiest:
            lines.append(f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} ({r['successes']}/{r['n']})")
        lines.append("")
    if hardest:
        lines.append("## Top 5 hardest tasks")
        lines.append("")
        for r in hardest:
            lines.append(f"- `{r['task_id']}` — pass^1 = {r['pass_hat_1']:.2f} ({r['successes']}/{r['n']})")
        lines.append("")

    # Examples
    success_examples = _pick_examples(results_by_task, want_success=True, limit=3)
    fail_examples = _pick_examples(results_by_task, want_success=False, limit=3)

    if success_examples:
        lines.append("## Example successful trajectories")
        lines.append("")
        for ex in success_examples:
            _emit_trajectory_block(lines, ex, success=True)

    if fail_examples:
        lines.append("## Example failed trajectories")
        lines.append("")
        for ex in fail_examples:
            _emit_trajectory_block(lines, ex, success=False)

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
    lines.append(f"### `{task_id}` — {'✅' if success else '❌'} reward={ep.get('reward')}")
    lines.append("")
    if not success and ep.get("db_diff"):
        lines.append("DB diff summary:")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(ep["db_diff"], indent=2)[:1500])
        lines.append("```")
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
