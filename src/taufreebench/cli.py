"""tau-free-bench CLI — all benchmark commands."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(help="tau-free-bench: Free-first LLM agent benchmark.")
console = Console()


@app.command("seed-data")
def seed_data(
    domain: Annotated[str, typer.Option("--domain", "-d")] = "retail",
):
    """Verify seed data files exist for a domain."""
    console.print(f"[bold]Checking seed data for domain: {domain}[/bold]")
    if domain == "retail":
        from taufreebench.domains.retail.seed_data import seed_retail_data
        seed_retail_data()
    else:
        console.print(f"[yellow]No seed data generator for domain '{domain}'.[/yellow]")
    console.print("[green]Done.[/green]")


@app.command("discover-free-models")
def discover_free_models():
    """List all known free models and their availability."""
    from taufreebench.providers.free_model_discovery import discover_free_models as _discover

    candidates = _discover()
    table = Table(title="Free Model Candidates", show_lines=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("Available", style="bold")
    table.add_column("Local")
    table.add_column("API Key Required")
    table.add_column("Notes / Pull Command")

    for c in candidates:
        avail = "[green]✓[/green]" if c.available else "[red]✗[/red]"
        local = "yes" if c.local else "no"
        req_key = "yes" if c.requires_api_key else "no"
        note = c.pull_command if c.pull_command else c.notes
        table.add_row(c.provider, c.model, avail, local, req_key, note)

    console.print(table)
    available = [c for c in candidates if c.available]
    console.print(f"\n[bold]{len(available)}/{len(candidates)}[/bold] models available.")


@app.command("calibrate-free-models")
def calibrate_free_models(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    user: Annotated[str, typer.Option("--user")] = "scripted",
    max_models: Annotated[int, typer.Option("--max-models")] = 6,
):
    """Benchmark available free models on calibration tasks and pick the best."""
    console.print(f"[bold]Calibrating free models for domain: {domain}[/bold]")
    from taufreebench.providers.calibration import run_calibration

    results = run_calibration(domain=domain, max_models=max_models)
    if not results:
        console.print("[red]No models calibrated.[/red]")
        return

    table = Table(title="Calibration Results", show_lines=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("pass^1", style="bold green")
    table.add_column("Invalid Tool Rate")
    table.add_column("Latency (s)")
    table.add_column("Selected")

    for i, r in enumerate(results):
        lat = f"{r['mean_latency_seconds']:.1f}" if r["mean_latency_seconds"] else "—"
        selected = "[green]★ yes[/green]" if i == 0 else "no"
        table.add_row(r["provider"], r["model"], f"{r['pass_1']:.2f}", f"{r['invalid_tool_call_rate']:.2f}", lat, selected)

    console.print(table)


@app.command("run-episode")
def run_episode(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    task: Annotated[str, typer.Option("--task")] = "retail_task_001",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    """Run a single episode for a task."""
    console.print(f"[bold]Running episode: domain={domain} task={task} agent={agent} user={user}[/bold]")
    from taufreebench.runners.run_episode import run_episode_for_task

    try:
        result = run_episode_for_task(
            domain=domain,
            task_id=task,
            agent_type=agent,
            agent_model=agent_model,
            user_type=user,
            user_model=user_model,
        )
    except Exception as e:
        console.print(f"[red]Error running episode: {e}[/red]")
        raise typer.Exit(1)

    reward_color = "green" if result.reward == 1 else "red"
    console.print(f"\n[bold]Result:[/bold]")
    console.print(f"  Reward: [{reward_color}]{result.reward}[/{reward_color}]  (action={result.action_reward}, output={result.output_reward})")
    console.print(f"  Turns: {result.turns}  Tool calls: {result.tool_calls}  Invalid: {result.invalid_tool_calls}")
    if result.failure_reason:
        console.print(f"  Failure: [yellow]{result.failure_reason}[/yellow]")
    if result.latency_seconds:
        console.print(f"  Latency: {result.latency_seconds:.1f}s")

    if result.db_diff:
        console.print(f"\n[yellow]DB diff (expected vs actual):[/yellow]")
        console.print(json.dumps(result.db_diff, indent=2)[:2000])

    if verbose:
        console.print("\n[bold]Trajectory:[/bold]")
        for step in result.trajectory:
            role = step.role
            content = step.content
            if role == "user":
                console.print(f"  [blue]User:[/blue] {content.get('content', '') if isinstance(content, dict) else content}")
            elif role == "agent":
                if isinstance(content, dict) and content.get("name"):
                    console.print(f"  [cyan]Agent→Tool:[/cyan] {content.get('name')}({json.dumps(content.get('arguments', {}))[:100]})")
                else:
                    console.print(f"  [cyan]Agent:[/cyan] {content.get('content', '') if isinstance(content, dict) else content}")
            elif role == "tool":
                if isinstance(content, dict):
                    console.print(f"  [magenta]Tool[{content.get('name','')}]:[/magenta] {str(content.get('result',''))[:200]}")


@app.command("run-benchmark")
def run_benchmark_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
):
    """Run the full benchmark and print aggregated metrics."""
    k_values = k or [1]
    console.print(f"[bold]Benchmark: domain={domain} agent={agent} user={user} trials={trials} k={k_values}[/bold]")

    from taufreebench.runners.run_benchmark import run_benchmark
    from taufreebench.core.metrics import compute_metrics

    with console.status("Running benchmark..."):
        results_by_task = run_benchmark(
            domain=domain,
            agent_type=agent,
            agent_model=agent_model,
            user_type=user,
            trials=trials,
        )

    metrics = compute_metrics(results_by_task, k_values=k_values)

    # Per-task table
    table = Table(title=f"Benchmark Results ({domain}, agent={agent})", show_lines=True)
    table.add_column("Task ID", style="cyan")
    table.add_column("Trials")
    table.add_column("Successes")
    for kv in k_values:
        table.add_column(f"pass^{kv}", style="green")
    for kv in k_values:
        table.add_column(f"pass@{kv}", style="blue")

    for row in metrics.get("per_task", []):
        cols = [row["task_id"], str(row["n"]), str(row["successes"])]
        for kv in k_values:
            cols.append(f"{row.get(f'pass_hat_{kv}', 0):.2f}")
        for kv in k_values:
            cols.append(f"{row.get(f'pass_at_{kv}', 0):.2f}")
        table.add_row(*cols)

    console.print(table)

    console.print("\n[bold]Aggregate Metrics:[/bold]")
    for kv in k_values:
        console.print(f"  pass^{kv}: [green]{metrics.get(f'pass_hat_{kv}', 0):.3f}[/green]  pass@{kv}: [blue]{metrics.get(f'pass_at_{kv}', 0):.3f}[/blue]")
    console.print(f"  Avg turns: {metrics.get('avg_turns', 0):.1f}  Avg tool calls: {metrics.get('avg_tool_calls', 0):.1f}")
    console.print(f"  Invalid tool call rate: {metrics.get('invalid_tool_call_rate', 0):.3f}")
    console.print(f"  Max-turn failure rate: {metrics.get('max_turn_failure_rate', 0):.3f}")


@app.command("benchmark-free-models")
def benchmark_free_models(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    user: Annotated[str, typer.Option("--user")] = "scripted",
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
    include_hosted: Annotated[bool, typer.Option("--include-hosted")] = False,
    max_models: Annotated[int, typer.Option("--max-models")] = 10,
):
    """Benchmark every available free model."""
    k_values = k or [1]
    from taufreebench.providers.free_model_discovery import discover_free_models as _discover
    from taufreebench.runners.run_benchmark import run_benchmark
    from taufreebench.core.metrics import compute_metrics

    candidates = [c for c in _discover() if c.available]
    if not include_hosted:
        candidates = [c for c in candidates if c.local]
    if not candidates:
        console.print("[yellow]No available free models found. Run discover-free-models for setup instructions.[/yellow]")
        return

    candidates = candidates[:max_models]
    console.print(f"[bold]Benchmarking {len(candidates)} free model(s) on {domain}...[/bold]")

    summary_rows: list[dict] = []
    for c in candidates:
        agent_type = c.provider
        if agent_type == "ollama":
            agent_model = c.model
        else:
            agent_model = c.model
        console.print(f"\n  [{c.provider}] {c.model}")
        try:
            results = run_benchmark(
                domain=domain,
                agent_type=agent_type,
                agent_model=agent_model,
                user_type=user,
                trials=trials,
            )
            m = compute_metrics(results, k_values=k_values)
            row: dict = {"provider": c.provider, "model": c.model, **{f"pass_hat_{kv}": m.get(f"pass_hat_{kv}", 0) for kv in k_values}, **{f"pass_at_{kv}": m.get(f"pass_at_{kv}", 0) for kv in k_values}, "avg_turns": m.get("avg_turns", 0), "avg_tool_calls": m.get("avg_tool_calls", 0), "invalid_rate": m.get("invalid_tool_call_rate", 0), "latency": m.get("mean_latency_seconds")}
            summary_rows.append(row)
        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")

    if not summary_rows:
        return

    table = Table(title="Free Model Benchmark Results", show_lines=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="magenta")
    for kv in k_values:
        table.add_column(f"pass^{kv}", style="green")
    for kv in k_values:
        table.add_column(f"pass@{kv}", style="blue")
    table.add_column("Avg Turns")
    table.add_column("Avg Tools")
    table.add_column("Invalid Rate")
    table.add_column("Latency (s)")

    for r in summary_rows:
        cols = [r["provider"], r["model"]]
        for kv in k_values:
            cols.append(f"{r.get(f'pass_hat_{kv}', 0):.2f}")
        for kv in k_values:
            cols.append(f"{r.get(f'pass_at_{kv}', 0):.2f}")
        cols += [f"{r['avg_turns']:.1f}", f"{r['avg_tool_calls']:.1f}", f"{r['invalid_rate']:.3f}", f"{r['latency']:.1f}" if r['latency'] else "—"]
        table.add_row(*cols)

    console.print(table)


@app.command("inspect-task")
def inspect_task(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    task: Annotated[str, typer.Option("--task")] = "retail_task_001",
):
    """Show full task details including instruction and expected actions."""
    from taufreebench.runners.run_episode import _get_data_dir, _load_tasks

    data_dir = _get_data_dir(domain)
    tasks = _load_tasks(domain, data_dir)
    task_map = {t.id: t for t in tasks}

    if task not in task_map:
        console.print(f"[red]Task '{task}' not found.[/red]")
        console.print(f"Available: {list(task_map.keys())}")
        raise typer.Exit(1)

    t = task_map[task]
    console.print(f"[bold]Task: {t.id}[/bold]")
    console.print(f"[bold]Tags:[/bold] {', '.join(t.tags)}")
    console.print(f"[bold]Max turns:[/bold] {t.max_turns}")
    console.print(f"\n[bold]Instruction:[/bold]")
    console.print(f"  {t.instruction}")
    console.print(f"\n[bold]Expected Actions ({len(t.expected_actions)}):[/bold]")
    for action in t.expected_actions:
        console.print(f"  {action.name}({json.dumps(action.arguments, indent=4)})")
    if t.required_outputs:
        console.print(f"\n[bold]Required Outputs:[/bold]")
        for r in t.required_outputs:
            console.print(f"  - '{r}'")


@app.command("analyze-failures")
def analyze_failures_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    trials: Annotated[int, typer.Option("--trials")] = 1,
):
    """Analyze failure modes across benchmark results."""
    from taufreebench.runners.run_benchmark import run_benchmark
    from taufreebench.runners.analyze_failures import analyze_failures, FAILURE_GROUPS

    with console.status("Running benchmark for failure analysis..."):
        results = run_benchmark(
            domain=domain,
            agent_type=agent,
            agent_model=agent_model,
            user_type=user,
            trials=trials,
        )

    analysis = analyze_failures(results)

    console.print(f"\n[bold]Failure Analysis[/bold]")
    console.print(f"  Total trials: {analysis['total_trials']}")
    console.print(f"  Total failures: {analysis['total_failures']}  ({analysis['failure_rate']:.1%} failure rate)")

    table = Table(title="Failure Breakdown", show_lines=True)
    table.add_column("Category", style="red")
    table.add_column("Count")
    table.add_column("Affected Tasks")

    for group in FAILURE_GROUPS:
        info = analysis["groups"].get(group, {"count": 0, "task_ids": []})
        if info["count"] > 0:
            table.add_row(group, str(info["count"]), ", ".join(sorted(info["task_ids"])))

    console.print(table)


@app.command("validate-dataset")
def validate_dataset_cmd(
    domain: Annotated[str, typer.Option("--domain", "-d")] = "retail",
):
    """Validate all tasks: replay expected_actions and check references."""
    from taufreebench.runners.validate_dataset import validate_dataset

    console.print(f"[bold]Validating dataset for domain: {domain}[/bold]")
    results = validate_dataset(domain)

    table = Table(title=f"Dataset Validation ({domain})", show_lines=True)
    table.add_column("Task ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Error")

    any_invalid = False
    for r in results:
        status_str = "[green]ok[/green]" if r["status"] == "ok" else "[red]invalid[/red]"
        err_str = "; ".join(r["errors"]) if r["errors"] else "—"
        if r["status"] != "ok":
            any_invalid = True
        table.add_row(r["task_id"], status_str, err_str)

    console.print(table)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    console.print(f"\n[bold]{ok_count}/{len(results)}[/bold] tasks valid.")

    if any_invalid:
        raise typer.Exit(1)


@app.command("report-results")
def report_results_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
):
    """Run the benchmark and save episodes/metrics/report to runs/<timestamp>/."""
    k_values = k or [1]
    console.print(f"[bold]Reporting: domain={domain} agent={agent} user={user} trials={trials} k={k_values}[/bold]")

    from taufreebench.runners.run_benchmark import run_benchmark
    from taufreebench.runners.run_episode import _get_data_dir, _load_tasks
    from taufreebench.runners.report import write_report
    from taufreebench.core.metrics import compute_metrics

    with console.status("Running benchmark..."):
        results_by_task = run_benchmark(
            domain=domain,
            agent_type=agent,
            agent_model=agent_model,
            user_type=user,
            trials=trials,
        )

    metrics = compute_metrics(results_by_task, k_values=k_values)
    tasks = _load_tasks(domain, _get_data_dir(domain))
    tasks_by_id = {t.id: t for t in tasks}

    report_path = write_report(
        domain=domain,
        agent=agent,
        agent_model=agent_model,
        user_simulator=user,
        trials=trials,
        k_values=k_values,
        results_by_task=results_by_task,
        metrics=metrics,
        tasks_by_id=tasks_by_id,
    )
    console.print(f"\n[bold green]Report written:[/bold green] {report_path}")
    console.print(f"  Per-run dir: {report_path.parent}")
    console.print(f"  episodes.json: {report_path.parent / 'episodes.json'}")
    console.print(f"  metrics.json:  {report_path.parent / 'metrics.json'}")
    console.print(f"\n[bold]Aggregate:[/bold]")
    for kv in k_values:
        console.print(f"  pass^{kv}: {metrics.get(f'pass_hat_{kv}', 0):.3f}  pass@{kv}: {metrics.get(f'pass_at_{kv}', 0):.3f}")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
