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
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
):
    """Run the benchmark and save episodes/metrics/report to runs/<timestamp>/."""
    k_values = k or [1]
    console.print(f"[bold]Reporting: domain={domain} agent={agent} user={user} trials={trials} k={k_values}[/bold]")

    from taufreebench.runners.run_benchmark import run_benchmark
    from taufreebench.runners.run_episode import _get_data_dir, _load_tasks
    from taufreebench.runners.report import write_report, _determine_validity
    from taufreebench.core.metrics import compute_metrics

    _, validity_banner = _determine_validity(agent, user)
    console.print(f"\n[yellow]{validity_banner}[/yellow]\n")

    with console.status("Running benchmark..."):
        results_by_task = run_benchmark(
            domain=domain,
            agent_type=agent,
            agent_model=agent_model,
            user_type=user,
            user_model=user_model,
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
        user_model=user_model,
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


@app.command("audit-paper-validity")
def audit_paper_validity_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    run: Annotated[Optional[str], typer.Option("--run")] = None,
):
    """Print a paper-validity checklist for a run (or current dataset if no run given)."""
    import os
    from pathlib import Path

    console.print(f"\n[bold]Paper-Validity Audit — domain={domain}[/bold]")
    console.print("[dim]This is a clean-room τ-bench-style mini benchmark, not the original τ-bench benchmark.[/dim]\n")

    # --- Load run metadata ---
    run_meta: dict = {}
    if run:
        run_path = Path(run)
        metrics_file = run_path / "metrics.json"
        if metrics_file.exists():
            run_meta = json.loads(metrics_file.read_text()).get("run_metadata", {})
        else:
            console.print(f"[yellow]No metrics.json found in {run_path}[/yellow]")

    agent = run_meta.get("agent", "unknown")
    user_sim = run_meta.get("user_simulator", "unknown")
    task_count = run_meta.get("task_count", "?")
    trials = run_meta.get("trials", "?")
    k_values = run_meta.get("k_values", [])
    git_hash = run_meta.get("git_commit", "unknown")
    dataset_hash = run_meta.get("dataset_hash", "unknown")
    validity_mode = run_meta.get("validity_mode", "unknown")

    is_llm_agent = agent not in ("rule", "unknown")
    is_llm_user = user_sim not in ("scripted", "unknown")

    def chk(ok: bool, label: str, detail: str = "") -> None:
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        detail_str = f"  [dim]{detail}[/dim]" if detail else ""
        console.print(f"  {mark}  {label}{detail_str}")

    # Section A: Environment loop
    table_a = Table(title="A. Environment Loop", show_lines=True)
    table_a.add_column("Check")
    table_a.add_column("Status")
    table_a.add_column("Notes")
    table_a.add_row("Agent sees only policy, tools, conversation, tool results", "[green]✓[/green]", "by design")
    table_a.add_row("User does not see tool calls/results", "[green]✓[/green]", "by design")
    table_a.add_row("Tools mutate JSON DB", "[green]✓[/green]", "by design")
    table_a.add_row("Final DB-state comparison used", "[green]✓[/green]", "strict evaluator")
    console.print(table_a)
    console.print()

    # Section B: Evaluation
    table_b = Table(title="B. Evaluation", show_lines=True)
    table_b.add_column("Check")
    table_b.add_column("Status")
    table_b.add_column("Notes")
    table_b.add_row("Expected DB via strict replay of expected_actions", "[green]✓[/green]", "raises DatasetValidationError if invalid")
    table_b.add_row("Final DB exact-match diff used", "[green]✓[/green]", "compute_db_diff()")
    table_b.add_row("Required outputs checked", "[green]✓[/green]", "substring search in agent messages")
    table_b.add_row("No LLM judge used", "[green]✓[/green]", "deterministic")
    table_b.add_row("pass^k implemented", "[green]✓[/green]", f"k={k_values}")
    table_b.add_row("pass@k implemented", "[green]✓[/green]", f"k={k_values}")
    console.print(table_b)
    console.print()

    # Section C: Comparability
    table_c = Table(title="C. Comparability to τ-bench Paper", show_lines=True)
    table_c.add_column("Criterion")
    table_c.add_column("This Run")
    table_c.add_column("Paper")

    agent_ok = "[green]yes[/green]" if is_llm_agent else "[red]no (rule-based)[/red]"
    user_ok = "[green]yes[/green]" if is_llm_user else "[red]no (scripted)[/red]"
    table_c.add_row("LLM agent", agent_ok, "yes (GPT-4o, Claude-3.5)")
    table_c.add_row("LLM user simulator", user_ok, "yes (GPT-4o)")
    table_c.add_row("Retail task count", str(task_count), "115")
    table_c.add_row("Airline task count", "not run" if domain != "airline" else str(task_count), "128")
    table_c.add_row("Trials", str(trials), "5")
    table_c.add_row("k values tested", str(k_values), "[1,2,3,4,5]")
    table_c.add_row("Dataset", "custom mini (this repo)", "original τ-bench")
    table_c.add_row("Git commit", git_hash, "—")
    table_c.add_row("Dataset hash", dataset_hash, "—")
    console.print(table_c)
    console.print()

    # Verdict
    if not is_llm_agent:
        verdict = "[red]NOT paper-comparable.[/red] Rule-based agent = deterministic sanity check only."
    elif not is_llm_user:
        verdict = "[yellow]PARTIALLY comparable.[/yellow] LLM agent + scripted user ≠ paper-style interaction."
    elif is_llm_agent and is_llm_user:
        verdict = "[yellow]CLOSEST to paper-style in this repo.[/yellow] Still custom/smaller — not original τ-bench."
    else:
        verdict = "[dim]Comparability unclear.[/dim]"

    console.print(f"[bold]Verdict:[/bold] {verdict}")
    console.print()
    console.print("[bold]This project is an educational, clean-room, mini τ-bench-style benchmark.[/bold]")
    console.print("[bold]It is not the original τ-bench and its scores are not directly comparable to the paper.[/bold]")


@app.command("dataset-stats")
def dataset_stats_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
):
    """Print dataset statistics for a domain."""
    from taufreebench.core.db import load_domain_db
    from taufreebench.runners.run_episode import _get_data_dir, _load_tasks
    from collections import Counter

    if domain == "retail":
        import taufreebench.domains.retail.tools  # noqa: F401

    data_dir = _get_data_dir(domain)
    db = load_domain_db(domain, data_dir)
    tasks = _load_tasks(domain, data_dir)

    users = db.get("users", {})
    products = db.get("products", {})
    orders = db.get("orders", {})

    # Count variants
    total_variants = sum(len(p.get("variants", {})) for p in products.values())

    # Count orders by status
    status_counter: Counter = Counter()
    for o in orders.values():
        status_counter[o.get("status", "unknown")] += 1

    # Task stats
    tag_counter: Counter = Counter()
    write_tasks = 0
    read_tasks = 0
    compound_tasks = 0
    tasks_with_outputs = 0
    single_action_tasks = 0
    total_expected_actions = 0

    for task in tasks:
        for tag in task.tags:
            tag_counter[tag] += 1
        if "compound" in task.tags:
            compound_tasks += 1
        if task.required_outputs:
            tasks_with_outputs += 1
        if len(task.expected_actions) == 1:
            single_action_tasks += 1
        if len(task.expected_actions) == 0:
            read_tasks += 1
        else:
            write_tasks += 1
        total_expected_actions += len(task.expected_actions)

    avg_expected = total_expected_actions / len(tasks) if tasks else 0

    console.print(f"\n[bold]Dataset Statistics — {domain}[/bold]\n")

    table = Table(title="Database", show_lines=True)
    table.add_column("Entity")
    table.add_column("Count")
    table.add_row("Users", str(len(users)))
    table.add_row("Products", str(len(products)))
    table.add_row("Product variants", str(total_variants))
    for status, cnt in sorted(status_counter.items()):
        table.add_row(f"Orders ({status})", str(cnt))
    table.add_row("Orders (total)", str(len(orders)))
    console.print(table)
    console.print()

    table2 = Table(title="Tasks", show_lines=True)
    table2.add_column("Metric")
    table2.add_column("Value")
    table2.add_row("Total tasks", str(len(tasks)))
    table2.add_row("Write tasks (have expected_actions)", str(write_tasks))
    table2.add_row("Read-only tasks (no expected_actions)", str(read_tasks))
    table2.add_row("Compound tasks", str(compound_tasks))
    table2.add_row("Single-action tasks", str(single_action_tasks))
    table2.add_row("Tasks with required_outputs", str(tasks_with_outputs))
    table2.add_row("Avg expected actions per task", f"{avg_expected:.2f}")
    console.print(table2)
    console.print()

    tag_table = Table(title="Tasks by Tag", show_lines=True)
    tag_table.add_column("Tag")
    tag_table.add_column("Count")
    for tag, cnt in sorted(tag_counter.items(), key=lambda x: -x[1]):
        tag_table.add_row(tag, str(cnt))
    console.print(tag_table)


@app.command("task-leakage-check")
def task_leakage_check_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "retail",
    strict: Annotated[bool, typer.Option("--strict")] = False,
):
    """Heuristic check for potential task leakage / overfitting risks."""
    import re as _re
    from taufreebench.core.db import load_domain_db
    from taufreebench.runners.run_episode import _get_data_dir, _load_tasks

    if domain == "retail":
        import taufreebench.domains.retail.tools  # noqa: F401

    data_dir = _get_data_dir(domain)
    db = load_domain_db(domain, data_dir)
    tasks = _load_tasks(domain, data_dir)

    warnings: list[str] = []

    # Build a set of all product/item IDs
    all_item_ids: set[str] = set()
    for product in db.get("products", {}).values():
        all_item_ids.update(product.get("variants", {}).keys())

    no_output_count = 0
    single_action_count = 0
    item_id_revealed_count = 0
    direct_args_revealed = 0

    for task in tasks:
        # Check if task has no required_outputs
        if not task.required_outputs:
            no_output_count += 1

        # Check single-action tasks
        if len(task.expected_actions) == 1:
            single_action_count += 1

        # Check if instruction directly reveals item IDs
        found_items = _re.findall(r"item_\w+", task.instruction)
        if found_items:
            item_id_revealed_count += 1
            warnings.append(
                f"[yellow]Task {task.id}[/yellow]: instruction reveals item_ids {found_items} — "
                f"rule agent can rely on exact IDs directly from instruction."
            )

        # Check if expected action arguments appear verbatim in instruction
        for action in task.expected_actions:
            for k, v in action.arguments.items():
                if isinstance(v, str) and len(v) > 5 and v.lower() in task.instruction.lower():
                    direct_args_revealed += 1
                    break

    # Check if too many tasks have no required_outputs
    no_output_rate = no_output_count / len(tasks) if tasks else 0
    if no_output_rate > 0.7:
        warnings.append(
            f"[yellow]High rate of tasks without required_outputs[/yellow]: "
            f"{no_output_count}/{len(tasks)} ({no_output_rate:.0%}). "
            f"Missing output checks make evaluation easier to pass."
        )

    # Check for high single-action rate
    single_rate = single_action_count / len(tasks) if tasks else 0
    if single_rate > 0.6:
        warnings.append(
            f"[yellow]High rate of single-action tasks[/yellow]: "
            f"{single_action_count}/{len(tasks)} ({single_rate:.0%}). "
            f"Single-action tasks may be too easy for rule-based agents."
        )

    # Check if many expected action arguments are directly in instruction
    direct_rate = direct_args_revealed / len(tasks) if tasks else 0
    if direct_rate > 0.8:
        warnings.append(
            f"[yellow]Many tasks reveal expected argument values in instruction[/yellow]: "
            f"{direct_args_revealed}/{len(tasks)} ({direct_rate:.0%}). "
            f"Scripted user + rule agent may 'cheat' by parsing instruction directly."
        )

    console.print(f"\n[bold]Task Leakage Check — {domain}[/bold]\n")
    console.print(f"Tasks analyzed: {len(tasks)}")
    console.print(f"Tasks with item_ids in instruction: {item_id_revealed_count}/{len(tasks)}")
    console.print(f"Tasks with no required_outputs: {no_output_count}/{len(tasks)}")
    console.print(f"Single-action tasks: {single_action_count}/{len(tasks)}")
    console.print(f"Tasks with args directly in instruction: {direct_args_revealed}/{len(tasks)}")
    console.print()

    if warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for w in warnings:
            console.print(f"  • {w}")
        if strict:
            console.print("\n[red]--strict mode: exiting with code 1[/red]")
            raise typer.Exit(1)
    else:
        console.print("[green]No significant leakage risks detected.[/green]")


# ============================================================================
# Sierra V2 — Dual-control (τ²-bench-style) telecom commands
# ============================================================================


@app.command("seed-telecom-data")
def seed_telecom_data():
    """Verify telecom seed data files exist and report counts."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    data_dir = root / "data" / "telecom"

    files = ["agent_db.json", "user_device_db.json", "policy.md", "user_personas.json"]
    table = Table(title="Telecom Seed Data", show_lines=True)
    table.add_column("File", style="cyan")
    table.add_column("Exists", style="bold")
    table.add_column("Size (bytes)")

    all_ok = True
    for fname in files:
        p = data_dir / fname
        ok = p.exists()
        all_ok = all_ok and ok
        size = p.stat().st_size if ok else 0
        mark = "[green]yes[/green]" if ok else "[red]NO[/red]"
        table.add_row(fname, mark, str(size))
    console.print(table)

    if not all_ok:
        console.print(f"[red]Some seed files missing under {data_dir}.[/red]")
        raise typer.Exit(1)

    agent_db = json.loads((data_dir / "agent_db.json").read_text())
    user_db = json.loads((data_dir / "user_device_db.json").read_text())

    counts = Table(title="Telecom DB Counts", show_lines=True)
    counts.add_column("Entity")
    counts.add_column("Count", justify="right")
    counts.add_row("customers", str(len(agent_db.get("customers", {}))))
    counts.add_row("lines", str(len(agent_db.get("lines", {}))))
    counts.add_row("plans", str(len(agent_db.get("plans", {}))))
    counts.add_row("bills", str(len(agent_db.get("bills", {}))))
    counts.add_row("devices", str(len(user_db.get("devices", {}))))
    console.print(counts)
    console.print("[green]Telecom seed data OK.[/green]")


@app.command("generate-telecom-tasks")
def generate_telecom_tasks(
    count: Annotated[int, typer.Option("--count")] = 60,
):
    """Generate compositional telecom tasks via the task generator."""
    from taufreebench.domains.telecom import task_generator as tg
    from pathlib import Path

    console.print(f"[bold]Generating {count} telecom tasks...[/bold]")
    tasks = tg.generate_tasks(count=count)
    out = tg.DATA_DIR / "tasks.json"
    tg.save_tasks(tasks, out)
    console.print(f"[green]Wrote {len(tasks)} tasks to {out}[/green]")

    from collections import Counter
    by_issue = Counter(t.issue_type for t in tasks)
    by_n = Counter((t.difficulty or {}).get("n_subtasks") for t in tasks)
    by_persona = Counter(t.persona_id for t in tasks)
    console.print(f"  issue_type: {dict(by_issue)}")
    console.print(f"  n_subtasks: {dict(sorted(by_n.items(), key=lambda x: (x[0] is None, x[0])))}")
    console.print(f"  persona:    {dict(by_persona)}")


@app.command("validate-dual-dataset")
def validate_dual_dataset_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
):
    """Replay each task's solution actions; verify assertions flip FAIL→PASS."""
    if domain != "telecom":
        console.print(f"[red]Dual-control dataset validation only supports 'telecom' (got {domain!r}).[/red]")
        raise typer.Exit(1)

    import copy
    from taufreebench.runners.run_dual_episode import (
        load_telecom_dbs, load_telecom_tasks, apply_initializers,
    )
    from taufreebench.domains.telecom.agent_tools import AGENT_TOOLS
    from taufreebench.domains.telecom.user_tools import USER_TOOLS
    from taufreebench.domains.telecom.assertions import run_assertions

    base_agent_db, base_user_db = load_telecom_dbs()
    tasks = load_telecom_tasks()

    console.print(f"[bold]Validating {len(tasks)} dual-control tasks for domain '{domain}'...[/bold]")

    table = Table(title="Dual Dataset Validation", show_lines=False)
    table.add_column("Task", style="cyan")
    table.add_column("Issue", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    n_ok = 0
    n_pre_already_passing = 0
    n_replay_failed = 0
    n_post_failing = 0

    for task in tasks:
        agent_db = copy.deepcopy(base_agent_db)
        user_db = copy.deepcopy(base_user_db)
        apply_initializers(task, agent_db, user_db)

        # 1. Pre-check: at least one assertion should fail.
        pre = run_assertions(task.assertions or [], agent_db, user_db)
        if pre and all(r.get("passed") for r in pre):
            n_pre_already_passing += 1
            table.add_row(task.id, task.issue_type, "[yellow]bad-pre[/yellow]",
                          "all assertions already passing before solution")
            continue

        # 2. Replay actions.
        replay_err = None
        for idx, action in enumerate(task.solution_actions or []):
            actor = action.actor
            name = action.name
            args = action.arguments or {}
            try:
                if actor == "agent":
                    fn = AGENT_TOOLS.get(name)
                    if fn is None:
                        replay_err = f"action#{idx}: unknown agent tool '{name}'"
                        break
                    result = fn(agent_db, user_db, **args)
                else:
                    fn = USER_TOOLS.get(name)
                    if fn is None:
                        replay_err = f"action#{idx}: unknown user tool '{name}'"
                        break
                    result = fn(user_db, agent_db, **args)
                if isinstance(result, str) and result.startswith("Error"):
                    replay_err = f"action#{idx} {actor}.{name}: {result[:80]}"
                    break
            except Exception as exc:  # noqa: BLE001
                replay_err = f"action#{idx} {actor}.{name} raised: {exc}"
                break

        if replay_err:
            n_replay_failed += 1
            table.add_row(task.id, task.issue_type, "[red]replay[/red]", replay_err[:80])
            continue

        # 3. Post-check: all assertions should pass.
        post = run_assertions(task.assertions or [], agent_db, user_db)
        failing = [r for r in post if not r.get("passed")]
        if failing:
            n_post_failing += 1
            detail = "; ".join(f"{r['name']}({r.get('detail', '')})" for r in failing[:2])
            table.add_row(task.id, task.issue_type, "[red]post-fail[/red]", detail[:80])
            continue

        n_ok += 1
        table.add_row(task.id, task.issue_type, "[green]ok[/green]", f"{len(task.assertions)} assertions")

    console.print(table)
    console.print()
    summary = Table(title="Summary", show_lines=False)
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total tasks", str(len(tasks)))
    summary.add_row("OK", f"[green]{n_ok}[/green]")
    summary.add_row("Bad-pre (already-passing)", str(n_pre_already_passing))
    summary.add_row("Replay failed", str(n_replay_failed))
    summary.add_row("Post-fail (assertions)", str(n_post_failing))
    console.print(summary)

    any_invalid = (n_pre_already_passing + n_replay_failed + n_post_failing) > 0
    if any_invalid:
        raise typer.Exit(1)


@app.command("telecom-stats")
def telecom_stats_cmd():
    """Print telecom dataset statistics."""
    from collections import Counter
    from taufreebench.runners.run_dual_episode import (
        load_telecom_dbs, load_telecom_tasks,
    )

    agent_db, user_db = load_telecom_dbs()
    tasks = load_telecom_tasks()

    console.print(f"\n[bold]Telecom Dataset Statistics[/bold]\n")

    db_table = Table(title="Database", show_lines=True)
    db_table.add_column("Entity")
    db_table.add_column("Count", justify="right")
    db_table.add_row("customers", str(len(agent_db.get("customers", {}))))
    db_table.add_row("lines", str(len(agent_db.get("lines", {}))))
    db_table.add_row("plans", str(len(agent_db.get("plans", {}))))
    db_table.add_row("bills", str(len(agent_db.get("bills", {}))))
    db_table.add_row("devices", str(len(user_db.get("devices", {}))))
    console.print(db_table)
    console.print()

    by_issue: Counter = Counter(t.issue_type for t in tasks)
    by_persona: Counter = Counter((t.persona_id or "none") for t in tasks)
    by_n: Counter = Counter((t.difficulty or {}).get("n_subtasks", "?") for t in tasks)
    by_who: Counter = Counter((t.difficulty or {}).get("who_acts", "?") for t in tasks)

    task_table = Table(title="Tasks", show_lines=True)
    task_table.add_column("Metric")
    task_table.add_column("Value")
    task_table.add_row("Total tasks", str(len(tasks)))
    task_table.add_row("Issue types",
                      ", ".join(f"{k}={v}" for k, v in sorted(by_issue.items())))
    task_table.add_row("Personas",
                      ", ".join(f"{k}={v}" for k, v in sorted(by_persona.items())))
    task_table.add_row("Subtask counts",
                      ", ".join(f"{k}={v}" for k, v in sorted(by_n.items(),
                                                              key=lambda x: (x[0] is None, x[0]))))
    task_table.add_row("Who acts",
                      ", ".join(f"{k}={v}" for k, v in sorted(by_who.items())))
    avg_n = (sum((t.difficulty or {}).get("n_subtasks", 0) for t in tasks) / len(tasks)) if tasks else 0
    task_table.add_row("Avg subtasks/task", f"{avg_n:.2f}")
    task_table.add_row("Tasks with assertions",
                      str(sum(1 for t in tasks if t.assertions)))
    task_table.add_row("Tasks with solution_actions",
                      str(sum(1 for t in tasks if t.solution_actions)))
    console.print(task_table)


@app.command("run-dual-episode")
def run_dual_episode_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
    task: Annotated[str, typer.Option("--task")] = "telecom_001",
    mode: Annotated[str, typer.Option("--mode")] = "default",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    """Run a single dual-control episode for a telecom task."""
    if domain != "telecom":
        console.print(f"[red]Only domain='telecom' is supported in dual mode (got {domain!r}).[/red]")
        raise typer.Exit(1)

    # accept both 'no-user' and 'no_user' on the CLI
    mode_norm = mode.replace("-", "_")
    if mode_norm not in ("default", "no_user", "oracle_plan"):
        console.print(f"[red]Invalid mode '{mode}'. Use default | no-user | oracle-plan.[/red]")
        raise typer.Exit(1)

    console.print(
        f"[bold]Running dual episode: task={task} mode={mode_norm} "
        f"agent={agent} user={user}[/bold]"
    )

    from taufreebench.runners.run_dual_episode import run_dual_episode_for_task

    try:
        result = run_dual_episode_for_task(
            task_id=task, mode=mode_norm,
            agent_type=agent, agent_model=agent_model,
            user_type=user, user_model=user_model,
        )
    except Exception as e:
        console.print(f"[red]Error running dual episode: {type(e).__name__}: {e}[/red]")
        raise typer.Exit(1)

    color = "green" if result.reward == 1 else "red"
    console.print(f"\n[bold]Result:[/bold]")
    console.print(
        f"  Reward: [{color}]{result.reward}[/{color}] "
        f"(assertion={result.assertion_reward}, output={result.output_reward})"
    )
    console.print(
        f"  Turns: {result.turns}  Agent tools: {result.agent_tool_calls}  "
        f"User tools: {result.user_tool_calls}  "
        f"Invalid(A/U): {result.invalid_agent_tool_calls}/{result.invalid_user_tool_calls}"
    )
    console.print(f"  failure_class: [yellow]{result.failure_class}[/yellow]")
    if result.failure_reason:
        console.print(f"  failure_reason: {result.failure_reason}")
    if result.latency_seconds is not None:
        console.print(f"  Latency: {result.latency_seconds:.2f}s")

    fails = [a for a in result.assertion_results if not a.get("passed")]
    if fails:
        console.print(f"\n[yellow]Failing assertions ({len(fails)}/{len(result.assertion_results)}):[/yellow]")
        for a in fails[:8]:
            console.print(f"  - {a.get('name')}: {a.get('detail', '')}")

    if verbose:
        console.print("\n[bold]Trajectory:[/bold]")
        for step in result.trajectory:
            role = step.role
            content = step.content
            if role == "user":
                txt = content.get("content", "") if isinstance(content, dict) else str(content)
                console.print(f"  [blue]USER  :[/blue] {txt[:160]}")
            elif role == "agent":
                txt = content.get("content", "") if isinstance(content, dict) else str(content)
                console.print(f"  [cyan]AGENT :[/cyan] {txt[:160]}")
            elif role == "agent_tool":
                if isinstance(content, dict) and content.get("name"):
                    console.print(
                        f"  [magenta]A→TOOL:[/magenta] {content.get('name')}"
                        f"({json.dumps(content.get('args', content.get('arguments', {})), default=str)[:100]})"
                    )
                    if "result" in content:
                        console.print(f"    [dim]↳ {str(content.get('result'))[:140]}[/dim]")
            elif role == "user_tool":
                if isinstance(content, dict) and content.get("name"):
                    console.print(
                        f"  [magenta]U→TOOL:[/magenta] {content.get('name')}"
                        f"({json.dumps(content.get('args', content.get('arguments', {})), default=str)[:100]})"
                    )
                    if "result" in content:
                        console.print(f"    [dim]↳ {str(content.get('result'))[:140]}[/dim]")
            elif role == "environment":
                txt = content.get("content", "") if isinstance(content, dict) else str(content)
                console.print(f"  [dim]ENV   :[/dim] {str(txt)[:160]}")


@app.command("run-dual-benchmark")
def run_dual_benchmark_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
    mode: Annotated[str, typer.Option("--mode")] = "default",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
):
    """Run the dual-control benchmark in memory (no files saved). Quick iteration."""
    if domain != "telecom":
        console.print(f"[red]Only domain='telecom' is supported (got {domain!r}).[/red]")
        raise typer.Exit(1)
    mode_norm = mode.replace("-", "_")
    if mode_norm not in ("default", "no_user", "oracle_plan"):
        console.print(f"[red]Invalid mode '{mode}'.[/red]")
        raise typer.Exit(1)

    k_values = k or [1]

    from taufreebench.runners.run_dual_benchmark import run_dual_benchmark
    from taufreebench.runners.dual_report import compute_dual_metrics

    console.print(
        f"[bold]Dual benchmark: mode={mode_norm} agent={agent} user={user} "
        f"trials={trials} k={k_values}[/bold]"
    )
    results_by_task = run_dual_benchmark(
        domain=domain, mode=mode_norm,
        agent_type=agent, agent_model=agent_model,
        user_type=user, user_model=user_model,
        trials=trials,
    )
    metrics = compute_dual_metrics(results_by_task, k_values=k_values)

    console.print("\n[bold]Aggregate Metrics:[/bold]")
    for kv in k_values:
        console.print(
            f"  pass^{kv}: [green]{metrics.get(f'pass_hat_{kv}', 0):.3f}[/green]  "
            f"pass@{kv}: [blue]{metrics.get(f'pass_at_{kv}', 0):.3f}[/blue]"
        )
    console.print(f"  Avg turns: {metrics.get('avg_turns', 0):.2f}")
    console.print(
        f"  Avg agent/user tool calls: "
        f"{metrics.get('avg_agent_tool_calls', 0):.2f} / "
        f"{metrics.get('avg_user_tool_calls', 0):.2f}"
    )
    console.print(
        f"  Invalid agent/user tool rate: "
        f"{metrics.get('invalid_agent_tool_rate', 0):.3f} / "
        f"{metrics.get('invalid_user_tool_rate', 0):.3f}"
    )
    console.print(f"  Max-turn failure rate: {metrics.get('max_turn_failure_rate', 0):.3f}")
    console.print(f"  Assertion failure rate: {metrics.get('assertion_failure_rate', 0):.3f}")


@app.command("report-dual-results")
def report_dual_results_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
    mode: Annotated[str, typer.Option("--mode")] = "default",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
    parallel: Annotated[int, typer.Option("--parallel")] = 1,
):
    """Run full dual benchmark and save episodes/metrics/report.md/audit.md."""
    if domain != "telecom":
        console.print(f"[red]Only domain='telecom' is supported (got {domain!r}).[/red]")
        raise typer.Exit(1)
    mode_norm = mode.replace("-", "_")
    if mode_norm not in ("default", "no_user", "oracle_plan"):
        console.print(f"[red]Invalid mode '{mode}'.[/red]")
        raise typer.Exit(1)

    k_values = k or [1]

    from taufreebench.runners.run_dual_benchmark import run_dual_benchmark
    from taufreebench.runners.run_dual_episode import load_telecom_tasks
    from taufreebench.runners.dual_report import (
        compute_dual_metrics, write_dual_report, _determine_dual_validity,
    )

    _, banner = _determine_dual_validity(mode_norm, agent, user)
    console.print(f"\n[yellow]{banner}[/yellow]\n")
    console.print(
        f"[bold]Dual benchmark report: mode={mode_norm} agent={agent} user={user} "
        f"trials={trials} k={k_values} parallel={parallel}[/bold]"
    )

    results_by_task = run_dual_benchmark(
        domain=domain, mode=mode_norm,
        agent_type=agent, agent_model=agent_model,
        user_type=user, user_model=user_model,
        trials=trials, parallel=parallel,
    )
    metrics = compute_dual_metrics(results_by_task, k_values=k_values)

    tasks = load_telecom_tasks()
    tasks_by_id = {t.id: t for t in tasks}

    report_path = write_dual_report(
        domain=domain,
        mode=mode_norm,
        agent=agent,
        agent_model=agent_model,
        user_simulator=user,
        user_model=user_model,
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
    console.print(f"  audit.md:      {report_path.parent / 'audit.md'}")
    console.print(f"\n[bold]Aggregate:[/bold]")
    for kv in k_values:
        console.print(
            f"  pass^{kv}: {metrics.get(f'pass_hat_{kv}', 0):.3f}  "
            f"pass@{kv}: {metrics.get(f'pass_at_{kv}', 0):.3f}"
        )


@app.command("compare-dual-modes")
def compare_dual_modes_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
    agent: Annotated[str, typer.Option("--agent")] = "rule",
    agent_model: Annotated[Optional[str], typer.Option("--agent-model")] = None,
    user: Annotated[str, typer.Option("--user")] = "scripted",
    user_model: Annotated[Optional[str], typer.Option("--user-model")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    k: Annotated[Optional[list[int]], typer.Option("--k")] = None,
):
    """Run all three modes (default / no_user / oracle_plan) and write a comparison report."""
    if domain != "telecom":
        console.print(f"[red]Only domain='telecom' is supported (got {domain!r}).[/red]")
        raise typer.Exit(1)

    k_values = k or [1]
    modes = ["default", "no_user", "oracle_plan"]

    from datetime import datetime
    from pathlib import Path
    from taufreebench.runners.run_dual_benchmark import run_dual_benchmark
    from taufreebench.runners.run_dual_episode import load_telecom_tasks
    from taufreebench.runners.dual_report import (
        compute_dual_metrics, write_dual_report,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_root = Path(__file__).resolve().parents[2]
    comparison_dir = project_root / "runs" / f"{timestamp}_comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_telecom_tasks()
    tasks_by_id = {t.id: t for t in tasks}

    per_mode_metrics: dict[str, dict] = {}

    for mode in modes:
        console.print(f"\n[bold cyan]=== Mode: {mode} ===[/bold cyan]")
        results_by_task = run_dual_benchmark(
            domain=domain, mode=mode,
            agent_type=agent, agent_model=agent_model,
            user_type=user, user_model=user_model,
            trials=trials,
        )
        metrics = compute_dual_metrics(results_by_task, k_values=k_values)
        per_mode_metrics[mode] = metrics

        mode_dir = comparison_dir / mode
        write_dual_report(
            domain=domain, mode=mode,
            agent=agent, agent_model=agent_model,
            user_simulator=user, user_model=user_model,
            trials=trials, k_values=k_values,
            results_by_task=results_by_task,
            metrics=metrics,
            tasks_by_id=tasks_by_id,
            out_dir=mode_dir,
        )

    # Comparison summary
    lines: list[str] = []
    lines.append(f"# Sierra V2 Dual-Control Mode Comparison — {timestamp}")
    lines.append("")
    lines.append(f"Agent: `{agent}`" + (f" / `{agent_model}`" if agent_model else ""))
    lines.append(f"User: `{user}`" + (f" / `{user_model}`" if user_model else ""))
    lines.append(f"Trials per task: {trials}  •  k values: {k_values}")
    lines.append("")
    lines.append("## Per-mode metrics")
    lines.append("")
    cols = ["mode"]
    for kv in k_values:
        cols.append(f"pass^{kv}")
    for kv in k_values:
        cols.append(f"pass@{kv}")
    cols += ["avg_turns", "avg_agent_tools", "avg_user_tools",
             "invalid_agent_rate", "invalid_user_rate",
             "assertion_fail_rate"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for mode in modes:
        m = per_mode_metrics.get(mode, {})
        row = [mode]
        for kv in k_values:
            row.append(f"{m.get(f'pass_hat_{kv}', 0):.3f}")
        for kv in k_values:
            row.append(f"{m.get(f'pass_at_{kv}', 0):.3f}")
        row += [
            f"{m.get('avg_turns', 0):.2f}",
            f"{m.get('avg_agent_tool_calls', 0):.2f}",
            f"{m.get('avg_user_tool_calls', 0):.2f}",
            f"{m.get('invalid_agent_tool_rate', 0):.3f}",
            f"{m.get('invalid_user_tool_rate', 0):.3f}",
            f"{m.get('assertion_failure_rate', 0):.3f}",
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("Per-mode reports:")
    for mode in modes:
        lines.append(f"- `{mode}/report.md`")
    lines.append("")
    summary_path = comparison_dir / "comparison.md"
    summary_path.write_text("\n".join(lines))

    console.print(f"\n[bold green]Mode comparison report:[/bold green] {summary_path}")
    table = Table(title="Mode Comparison", show_lines=True)
    table.add_column("Mode", style="cyan")
    for kv in k_values:
        table.add_column(f"pass^{kv}", style="green")
    table.add_column("avg_turns")
    table.add_column("assert_fail_rate", style="red")
    for mode in modes:
        m = per_mode_metrics.get(mode, {})
        row = [mode]
        for kv in k_values:
            row.append(f"{m.get(f'pass_hat_{kv}', 0):.3f}")
        row.append(f"{m.get('avg_turns', 0):.2f}")
        row.append(f"{m.get('assertion_failure_rate', 0):.3f}")
        table.add_row(*row)
    console.print(table)


@app.command("audit-tau2-validity")
def audit_tau2_validity_cmd(
    domain: Annotated[str, typer.Option("--domain")] = "telecom",
    run: Annotated[Optional[str], typer.Option("--run")] = None,
):
    """Print τ²-bench validity checklist (env loop, evaluation, paper comparability)."""
    from pathlib import Path

    console.print(f"\n[bold]τ²-bench Validity Audit — domain={domain}[/bold]")
    console.print(
        "[dim]Clean-room educational mini τ²-bench-style benchmark. "
        "Not original τ²-bench.[/dim]\n"
    )

    run_meta: dict = {}
    if run:
        run_path = Path(run)
        metrics_file = run_path / "metrics.json"
        if metrics_file.exists():
            run_meta = json.loads(metrics_file.read_text()).get("run_metadata", {})
        else:
            console.print(f"[yellow]No metrics.json found in {run_path}[/yellow]")

    mode = run_meta.get("mode", "unknown")
    agent = run_meta.get("agent", "unknown")
    user_sim = run_meta.get("user_simulator", "unknown")
    task_count = run_meta.get("task_count", "?")
    trials = run_meta.get("trials", "?")
    k_values = run_meta.get("k_values", [])
    git_hash = run_meta.get("git_commit", "unknown")
    dataset_hash = run_meta.get("dataset_hash", "unknown")
    validity_mode = run_meta.get("validity_mode", "unknown")

    is_llm_agent = agent not in ("rule", "unknown")
    is_llm_user = user_sim not in ("scripted", "unknown") and mode != "no_user"

    # A. Environment loop
    ta = Table(title="A. Environment Loop (dual-control)", show_lines=True)
    ta.add_column("Check")
    ta.add_column("Status")
    ta.add_column("Notes")
    ta.add_row("Agent sees only policy, conversation, agent-tool results", "[green]ok[/green]", "by design")
    ta.add_row("User does NOT see agent tool calls/results", "[green]ok[/green]", "trajectory visibility flags")
    ta.add_row("User has own tool set & device DB", "[green]ok[/green]" if mode != "no_user" else "[yellow]n/a[/yellow]", "")
    ta.add_row("Tools mutate JSON DBs", "[green]ok[/green]", "by design")
    ta.add_row("Mode used", f"[cyan]{mode}[/cyan]", "default | no_user | oracle_plan")
    console.print(ta)
    console.print()

    # B. Evaluation
    tb = Table(title="B. Evaluation", show_lines=True)
    tb.add_column("Check")
    tb.add_column("Status")
    tb.add_column("Notes")
    tb.add_row("Outcome judged by post-state assertions", "[green]ok[/green]", "run_assertions()")
    tb.add_row("Required-output substring check", "[green]ok[/green]", "case-insensitive")
    tb.add_row("No LLM judge", "[green]ok[/green]", "deterministic")
    tb.add_row("pass^k implemented", "[green]ok[/green]", f"k={k_values}")
    tb.add_row("pass@k implemented", "[green]ok[/green]", f"k={k_values}")
    tb.add_row("Failure classification", "[green]ok[/green]",
               "success / assertion_failed / max_turns / invalid_*_tool / ...")
    console.print(tb)
    console.print()

    # C. Comparability
    tc = Table(title="C. Comparability to τ²-bench Paper", show_lines=True)
    tc.add_column("Criterion")
    tc.add_column("This Run")
    tc.add_column("Paper")
    tc.add_row("LLM agent",
               "[green]yes[/green]" if is_llm_agent else "[red]no (rule-based)[/red]",
               "yes")
    tc.add_row("LLM user (with tools)",
               "[green]yes[/green]" if is_llm_user else (
                   "[yellow]n/a (no-user mode)[/yellow]" if mode == "no_user"
                   else "[red]no (scripted)[/red]"),
               "yes")
    tc.add_row("Telecom task count", str(task_count), "~114")
    tc.add_row("Trials", str(trials), "typically 4-5")
    tc.add_row("Dataset", "custom 60-task mini", "original τ²-bench")
    tc.add_row("Git commit", git_hash, "—")
    tc.add_row("Dataset hash", dataset_hash, "—")
    tc.add_row("Validity mode", validity_mode, "—")
    console.print(tc)
    console.print()

    if mode == "no_user":
        verdict = "[yellow]Oracle-ish upper bound only (no-user). Not paper-comparable.[/yellow]"
    elif mode == "oracle_plan":
        verdict = "[yellow]Ablation only (oracle-plan). Not paper-comparable.[/yellow]"
    elif not is_llm_agent:
        verdict = "[red]NOT paper-comparable. Rule-based agent = deterministic sanity check only.[/red]"
    elif not is_llm_user:
        verdict = "[yellow]PARTIALLY comparable. LLM agent + scripted user ≠ paper-style interaction.[/yellow]"
    elif is_llm_agent and is_llm_user:
        verdict = "[yellow]CLOSEST to paper-style in this repo. Still custom/smaller — not original τ²-bench.[/yellow]"
    else:
        verdict = "[dim]Comparability unclear.[/dim]"

    console.print(f"[bold]Verdict:[/bold] {verdict}")
    console.print()
    console.print(
        "[bold]This project is an educational, clean-room, mini τ²-bench-style benchmark.[/bold]"
    )
    console.print(
        "[bold]It is not the original τ²-bench and its scores are not directly "
        "comparable to the paper.[/bold]"
    )


def main():
    from dotenv import load_dotenv
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
