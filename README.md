# tau-free-bench

A clean-room educational reimplementation of τ-bench — a benchmark for evaluating LLM tool agents in realistic customer service workflows.

> **This is not the original τ-bench. Scores are not comparable to the paper.**

---

## What It Is

- **Deterministic evaluation**: no LLM judge — score = 1 iff final DB state matches expected AND required output strings appear
- **25-task retail dataset**: authentication, order lookup, cancellation, returns, exchanges, address changes, policy questions
- **Four benchmark modes**: from deterministic sanity check to LLM agent + LLM user (closest to paper)
- **Free-first**: runs entirely locally with Ollama, no paid API required

## What It Is Not

- Not the original τ-bench (115 retail + 128 airline tasks, GPT-4o)
- Not a reproduction of the paper's results
- Not a claim about performance on the original benchmark

---

## Benchmark Results

**pass^k** = consistency (all k trials succeed). **pass@k** = capability (at least one of k succeeds).
Both V1 and V2 use `gpt-4-0613` at T=1.0 as the LLM user simulator (paper standard). Agent runs at T=0.0 where the model accepts it (claude-opus-4-7 and gpt-5.5 don't accept the parameter — they use the API default).

### V1 — τ-bench-style retail (single-control, 25 tasks × 3 trials)

| Agent | pass^1 | pass^2 | pass^3 | pass@1 | pass@2 | pass@3 | Run |
|-------|-------:|-------:|-------:|-------:|-------:|-------:|-----|
| **claude-opus-4-7** | **0.947** | **0.907** | **0.880** | **0.947** | **0.987** | **1.000** | [20260513_123357](runs/20260513_123357/report.md) |
| **gpt-5.5** | **0.947** | **0.907** | **0.880** | **0.947** | **0.987** | **1.000** | [20260513_124650](runs/20260513_124650/report.md) |

V1 is saturated for both frontier models (each passes 71/75 trials with identical histograms). The 25-task retail benchmark no longer discriminates between top-tier models — V2 (below) does.

### V2 — τ²-bench-style telecom dual-control (60 tasks × 3 trials)

V2 lives in [`tau-benchv2/`](tau-benchv2/). Both agent and user have tools and share an environment. Scores below use Mode 3 (default = LLM agent + LLM user, dual control).

| Agent | pass^1 | pass^2 | pass^3 | pass@1 | pass@2 | pass@3 | Run |
|-------|-------:|-------:|-------:|-------:|-------:|-------:|-----|
| **claude-opus-4-7** | **0.717** | **0.644** | **0.617** | **0.717** | **0.789** | **0.833** | [tau-benchv2/runs/20260514_115448](tau-benchv2/runs/20260514_115448/report.md) |
| **gpt-5.5** | 0.656 | 0.606 | 0.583 | 0.656 | 0.706 | 0.733 | [tau-benchv2/runs/20260514_115146](tau-benchv2/runs/20260514_115146/report.md) |

V2 is properly discriminating: a ~6-point gap between opus-4-7 and gpt-5.5 on pass^1, growing to 10 points on pass@3. Both models are well within the useful ~50–80% range where the benchmark can detect real capability differences.

**V2 fixes that lifted opus from 0.050 → 0.717:**
- Inject `device_id`/`line_id`/`customer_id` into the user simulator's hidden instruction (paper-aligned: users know their own phone IDs)
- Deterministic guardrail: reject premature `###TRANSFER###` unless the agent has actually called the transfer tool AND said the canonical confirmation; up to 2 reprompts
- Tighter user-simulator prompt (don't pressure agent to escalate; ask clarifying questions)
- Tighter agent prompt (don't skip diagnostic steps; full MMS workflow explicitly enumerated)
- Removed policy truncation (agent now sees the full 3,657-char telecom policy)
- See [tau-benchv2/tests/test_premature_transfer_guard.py](tau-benchv2/tests/test_premature_transfer_guard.py) for 9 unit tests on the transfer guardrail.

---

## How the Benchmark Works

Each episode:
1. A simulated user (scripted or LLM) sends an opening message
2. The agent calls one tool OR sends one message per turn
3. Tool calls execute deterministic Python functions against a JSON database
4. Episode ends when user sends `###STOP###`
5. Final DB state is diffed against the expected state from ground-truth actions

**Score = 1** iff `action_reward = 1` (DB matches) AND `output_reward = 1` (required strings in agent messages).

---

## Benchmark Modes

| Mode | Agent | User | Paper-comparable? |
|------|-------|------|-------------------|
| 1 | Rule-based | Scripted | ❌ Sanity check only |
| 2 | LLM | Scripted | ⚠️ Partial (controlled user) |
| **3** | **LLM** | **LLM** | **🟡 Closest (custom/smaller dataset)** |
| 4 | All free models | Scripted | ❌ Model ranking only |

---

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic typer rich python-dotenv httpx
```

**Verify the dataset:**
```bash
PYTHONPATH=src python -m taufreebench.cli validate-dataset --domain retail
PYTHONPATH=src python -m taufreebench.cli dataset-stats --domain retail
```

**Run one episode (no LLM needed):**
```bash
PYTHONPATH=src python -m taufreebench.cli run-episode \
  --domain retail --task retail_task_001 --agent rule --user scripted --verbose
```

**Run the paper-style benchmark (Mode 3):**
```bash
# Install Ollama: https://ollama.ai
ollama pull qwen3:8b && ollama pull llama3.1:8b

PYTHONPATH=src python -m taufreebench.cli report-results \
  --domain retail \
  --agent ollama --agent-model qwen3:8b \
  --user ollama --user-model llama3.1:8b \
  --trials 3 --k 1 --k 2 --k 3
```

**Audit paper validity:**
```bash
PYTHONPATH=src python -m taufreebench.cli audit-paper-validity \
  --domain retail --run runs/<TIMESTAMP>
```

---

## Optional Hosted Free Tiers

Copy `.env.example` to `.env` and add keys:

| Provider | Free tier | Key |
|----------|-----------|-----|
| Groq | [console.groq.com](https://console.groq.com/keys) | `GROQ_API_KEY` |
| Gemini | [aistudio.google.com](https://aistudio.google.com/app/apikey) | `GEMINI_API_KEY` |
| OpenRouter | [openrouter.ai](https://openrouter.ai/keys) | `OPENROUTER_API_KEY` |

```bash
PYTHONPATH=src python -m taufreebench.cli report-results \
  --domain retail --agent groq --user scripted --trials 3 --k 1 --k 2 --k 3
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `validate-dataset` | Strict replay of all expected actions — raises on any error |
| `dataset-stats` | DB entity counts, task breakdown by type and tag |
| `task-leakage-check` | Warn about item IDs or args visible in task instructions |
| `run-episode` | Run one episode with verbose trajectory output |
| `report-results` | Run full benchmark, save `episodes.json` + `metrics.json` + `report.md` |
| `audit-paper-validity` | 3-section checklist: environment loop, evaluation, paper comparability |
| `discover-free-models` | List all free model candidates and availability |
| `calibrate-free-models` | Rank free models on a small calibration set |
| `benchmark-free-models` | Benchmark all available free models in one shot |
| `analyze-failures` | Categorize failure modes across a run |

---

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
# 84 tests, 0 failures — no network calls, no API keys required
```

---

## Dataset

| Entity | Count |
|--------|-------|
| Users | 15 |
| Products / variants | 20 / 87 |
| Orders | 43 (16 pending, 19 delivered, 5 processed, 3 cancelled) |
| Tasks | 25 (20 write, 5 read-only, 3 compound) |

Task tags: `auth` (25), `delivered` (9), `modify` (8), `pending` (6), `return` (6), `cancel` (4), `exchange` (4), `compound` (3), `policy` (3)

---

## How to Cite

> "We evaluated [model] on a custom mini τ-bench-style retail benchmark (25 tasks, [N] trials). Results are not directly comparable to the original τ-bench paper (Yao et al. 2024). The benchmark uses the same evaluation methodology (DB-state comparison, pass^k/pass@k) but a smaller, custom dataset."

**Original paper**: Shunyu Yao et al., "τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains." arXiv 2024.

---

## Structure

```
tau-free-bench/
  data/retail/          # 15 users, 20 products, 43 orders, 25 tasks, policy
  src/taufreebench/
    core/               # types, DB, evaluator, metrics, diff
    domains/retail/     # tools + seed data
    agents/             # rule-based, Ollama, Groq, Gemini, OpenRouter
    users/              # scripted, Ollama, Groq, Gemini, OpenRouter
    providers/          # provider abstractions, model discovery, calibration
    runners/            # episode runner, benchmark runner, report writer
    cli.py
  tests/                # 84 pytest tests (no network)
  docs/                 # benchmark_validity.md, architecture.md, adding_domains.md
  runs/                 # saved benchmark reports
```

See [docs/benchmark_validity.md](docs/benchmark_validity.md) for full validity details and mode descriptions.
