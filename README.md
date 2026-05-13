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

### Mode 3 — LLM agent + LLM user (closest to paper)

Same user simulator (`llama3.1:8b`) across both rows — direct agent comparison:

| Agent | User sim | Tasks | Trials | pass^1 | pass@3 | Run |
|-------|----------|-------|--------|--------|--------|-----|
| **gpt-5.2** (OpenAI) | llama3.1:8b | 25 | 3 | **0.227** | **0.440** | [20260512_172751](runs/20260512_172751/report.md) |
| qwen3:8b (Ollama, local) | llama3.1:8b | 25 | 3 | 0.120 | 0.200 | [20260512_152713](runs/20260512_152713/report.md) |

For reference, gpt-5.2 also self-played: gpt-5.2 agent + gpt-5.2 user → pass^1 = 0.147, pass@3 = 0.160 ([run](runs/20260512_164757/report.md)). The stricter user simulator brings the score down.

### Mode 1 — Rule-based + scripted (sanity check, not an LLM score)

| Agent | Tasks | Trials | pass^1 |
|-------|-------|--------|--------|
| Rule-based state machine | 25 | 3 | **1.000** |

Run: [`runs/20260512_120058/`](runs/20260512_120058/report.md)

> Rule-based pass^1 = 1.000 confirms the pipeline and dataset are correct — it is not a meaningful LLM result.

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
