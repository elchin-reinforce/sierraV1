# tau-free-bench

A clean-room, from-scratch educational reimplementation of τ-bench — a benchmark for evaluating LLM tool agents in realistic customer service workflows.

**Free-first design**: defaults to local Ollama models and rule-based agents. No paid API required.

> **This project is an educational, clean-room, mini τ-bench-style benchmark. It is not the original τ-bench and its scores are not directly comparable to the paper.**

---

## What This Repo Is

- A benchmark framework with deterministic DB-state evaluation (no LLM judge)
- A 25-task mini retail dataset with realistic customer service scenarios
- A comparison harness for free/local LLMs (Ollama, Groq, Gemini, OpenRouter)
- An educational implementation of pass^k and pass@k metrics

## What This Repo Is Not

- Not the original τ-bench (which has 115 retail + 128 airline tasks)
- Not a reproduction of the paper's GPT-4o results
- Not a claim about any model's performance on the original benchmark

---

## How the Benchmark Works

In each episode:

1. A simulated user (scripted or LLM) sends a message to the agent
2. The agent can either **call one tool** or **send one message** per turn
3. Tool calls execute deterministic Python functions against a JSON database
4. The episode ends when the user sends `###STOP###`
5. The final database state is compared to the expected state from ground-truth actions

**Evaluation is fully deterministic** — no LLM judge. Score = 1 if and only if:
- The final DB matches the expected DB (`action_reward = 1`), AND
- All required output substrings appear in agent messages (`output_reward = 1`)

The evaluator uses **strict expected-action replay**: if any expected action references a missing tool or returns an error, a `DatasetValidationError` is raised rather than silently producing a wrong expected DB.

---

## Benchmark Modes

| Mode | Agent | User | Comparable to paper? | Use for |
|------|-------|------|----------------------|---------|
| 1 | rule | scripted | ❌ No | Deterministic sanity check |
| 2 | LLM | scripted | ⚠️ Partially | LLM tool-use with controlled user |
| 3 | LLM | LLM | 🟡 Closest (still mini) | End-to-end mini paper-style |
| 4 | all free models | scripted | ❌ No | Free model ranking |

See [docs/benchmark_validity.md](docs/benchmark_validity.md) for full details.

---

## How to Interpret Results

- **Rule-based + scripted scores are sanity checks**, not LLM benchmark scores
- **Scripted user results are easier** than LLM-user results (user always provides the right info)
- **This dataset has 25 tasks**, not 115 — scores are not comparable to the paper
- Always check the validity banner printed at the top of every report

---

## How pass^k Works

| Metric | Question answered |
|--------|-----------------|
| **pass^k** | "If I pick k random attempts, what fraction of k-subsets are all correct?" (measures consistency) |
| **pass@k** | "If I run k attempts, what's the probability at least one succeeds?" (measures raw capability) |

Both average over all tasks. `pass^1 = pass@1`.

---

## How to Produce a Valid Mini LLM Benchmark

```bash
# Step 1: Validate the dataset
python -m taufreebench.cli validate-dataset --domain retail

# Step 2: Check dataset stats  
python -m taufreebench.cli dataset-stats --domain retail

# Step 3: Run LLM agent with scripted user (partial LLM benchmark)
python -m taufreebench.cli report-results \
  --domain retail \
  --agent ollama --agent-model qwen3:8b \
  --user scripted \
  --trials 3 --k 1 --k 2 --k 3

# Step 4: Audit validity
python -m taufreebench.cli audit-paper-validity \
  --domain retail \
  --run runs/<LATEST_RUN>
```

---

## How to Cite/Describe This Project Honestly

> "We evaluated [model] on a custom mini τ-bench-style retail benchmark (25 tasks, [N] trials per task). Results are not directly comparable to the original τ-bench paper (Yao et al. 2024). The benchmark uses the same evaluation methodology (DB-state comparison, pass^k/pass@k metrics) but a smaller, custom dataset."

---

## Quick Start

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install hatchling pydantic typer rich python-dotenv httpx
# then add PYTHONPATH=src when running, or install package:
PYTHONPATH=src python -m taufreebench.cli seed-data --domain retail
```

### Verify data

```bash
PYTHONPATH=src python -m taufreebench.cli seed-data --domain retail
PYTHONPATH=src python -m taufreebench.cli validate-dataset --domain retail
PYTHONPATH=src python -m taufreebench.cli dataset-stats --domain retail
```

### Run one episode (no LLM needed)

```bash
PYTHONPATH=src python -m taufreebench.cli run-episode \
  --domain retail \
  --task retail_task_001 \
  --agent rule \
  --user scripted \
  --verbose
```

### Run the full benchmark (deterministic sanity check)

```bash
PYTHONPATH=src python -m taufreebench.cli report-results \
  --domain retail \
  --agent rule \
  --user scripted \
  --trials 3 \
  --k 1 --k 2 --k 3
```

### Audit paper validity

```bash
PYTHONPATH=src python -m taufreebench.cli audit-paper-validity \
  --domain retail \
  --run runs/<TIMESTAMP>
```

---

## Ollama Setup (free local LLMs)

```bash
# Install Ollama: https://ollama.ai
ollama serve   # in a separate terminal

# Pull recommended models
ollama pull qwen3:8b
ollama pull llama3.1:8b
ollama pull gemma3:4b
```

### Discover available free models

```bash
PYTHONPATH=src python -m taufreebench.cli discover-free-models
```

### Auto-calibrate to find the best available model

```bash
PYTHONPATH=src python -m taufreebench.cli calibrate-free-models \
  --domain retail \
  --user scripted \
  --max-models 6
```

### Run LLM benchmark with the best auto-selected model

```bash
PYTHONPATH=src python -m taufreebench.cli report-results \
  --domain retail \
  --agent auto-free \
  --user scripted \
  --trials 3 \
  --k 1 --k 2 --k 3
```

---

## Optional Hosted Free Tiers

Copy `.env.example` to `.env` and add API keys:

```bash
cp .env.example .env
```

**Gemini** (free tier at [aistudio.google.com](https://aistudio.google.com/app/apikey)):
```bash
export GEMINI_API_KEY="your-key"
```

**Groq** (free tier at [console.groq.com](https://console.groq.com/keys)):
```bash
export GROQ_API_KEY="your-key"
```

**OpenRouter** (free models at [openrouter.ai](https://openrouter.ai/keys)):
```bash
export OPENROUTER_API_KEY="your-key"
```

### Benchmark all free models including hosted

```bash
PYTHONPATH=src python -m taufreebench.cli benchmark-free-models \
  --domain retail \
  --include-hosted \
  --user scripted \
  --trials 2 \
  --k 1 --k 2
```

---

## All CLI Commands

| Command | Description |
|---------|-------------|
| `seed-data` | Verify seed data files exist |
| `validate-dataset` | Replay all expected actions; verify dataset integrity |
| `dataset-stats` | Print dataset statistics (users, products, tasks by tag) |
| `task-leakage-check` | Heuristic check for overfitting/leakage risks |
| `discover-free-models` | List all free model candidates and availability |
| `calibrate-free-models` | Rank free models on calibration tasks |
| `run-episode` | Run one task episode |
| `run-benchmark` | Run full benchmark, print metrics |
| `report-results` | Run benchmark and save report to `runs/<timestamp>/` |
| `benchmark-free-models` | Benchmark all available free models |
| `audit-paper-validity` | Print paper-validity checklist for a run |
| `inspect-task` | Show task details |
| `analyze-failures` | Categorize failure modes |

---

## Running Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

All tests run without any API keys or Ollama. Network is never called in tests.

---

## Project Structure

```
tau-free-bench/
  data/
    retail/          # 10 users, 12 products, 20 orders, 25 tasks, policy
    airline/         # airline domain
  src/taufreebench/
    core/            # types, DB, tool registry, environment, evaluator, metrics, diff
    domains/         # retail and airline tools + seed data
    users/           # scripted, Ollama, Gemini, Groq, OpenRouter users
    agents/          # rule-based, Ollama, Gemini, Groq, OpenRouter, ReAct agents
    providers/       # provider abstractions, model discovery, calibration
    runners/         # episode runner, benchmark runner, failure analyzer, report
    cli.py           # Typer CLI
  tests/             # pytest tests (no network calls)
  docs/
    benchmark_validity.md  # Validity guide and benchmark modes
    architecture.md
    adding_domains.md
    free_models.md
  runs/              # Generated benchmark run reports
```

---

## Adding Domains

See [docs/adding_domains.md](docs/adding_domains.md).

## Adding Providers

See [docs/free_models.md](docs/free_models.md).

## Benchmark Validity Details

See [docs/benchmark_validity.md](docs/benchmark_validity.md).
