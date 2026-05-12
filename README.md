# tau-free-bench

A clean-room, from-scratch educational reimplementation of τ-bench — a benchmark for evaluating LLM tool agents in realistic customer service workflows.

**Free-first design**: defaults to local Ollama models and rule-based agents. No paid API required.

---

## What it does

`tau-free-bench` measures how well an agent can complete realistic customer service tasks. In each episode:

1. A simulated user (scripted or LLM) sends a message to the agent
2. The agent can either **call one tool** or **send one message** per turn
3. Tool calls execute deterministic Python functions against a JSON database
4. The episode ends when the user says `###STOP###`
5. The final database state is compared to the expected state from ground-truth actions

**Evaluation is fully deterministic** — no LLM judge. Score = 1 if and only if:
- The final DB matches the expected DB (action_reward = 1), AND
- All required output substrings appear in agent messages (output_reward = 1)

---

## Why final DB-state evaluation matters

Action-sequence matching (did the agent call the right tool?) is brittle — equivalent actions can differ in argument format. DB-state comparison is robust: it checks the observable effect of the agent's actions, not the exact path taken.

---

## pass^k vs pass@k

| Metric | Question answered |
|--------|-----------------|
| **pass^k** | "If I pick k random attempts, what fraction of k-subsets are all correct?" (measures consistency) |
| **pass@k** | "If I run k attempts, what's the probability at least one succeeds?" (measures capability) |

Both average over all tasks. `pass^1 = pass@1`.

---

## Quick Start

### Install

```bash
pip install -e ".[dev]"
```

### Verify data

```bash
python -m taufreebench.cli seed-data --domain retail
```

### Run one episode (no LLM needed)

```bash
python -m taufreebench.cli run-episode \
  --domain retail \
  --task retail_task_001 \
  --agent rule \
  --user scripted \
  --verbose
```

### Run the full benchmark (rule-based baseline)

```bash
python -m taufreebench.cli run-benchmark \
  --domain retail \
  --agent rule \
  --user scripted \
  --trials 1 \
  --k 1
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
python -m taufreebench.cli discover-free-models
```

### Auto-calibrate to find the best available model

```bash
python -m taufreebench.cli calibrate-free-models \
  --domain retail \
  --user scripted \
  --max-models 6
```

### Run benchmark with the best auto-selected model

```bash
python -m taufreebench.cli run-benchmark \
  --domain retail \
  --agent auto-free \
  --user scripted \
  --trials 3 \
  --k 1 \
  --k 2 \
  --k 3
```

### Run a specific Ollama model

```bash
python -m taufreebench.cli run-episode \
  --domain retail \
  --task retail_task_001 \
  --agent ollama \
  --agent-model qwen3:8b \
  --user scripted
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
python -m taufreebench.cli benchmark-free-models \
  --domain retail \
  --include-hosted \
  --user scripted \
  --trials 2 \
  --k 1 \
  --k 2
```

---

## All CLI Commands

| Command | Description |
|---------|-------------|
| `seed-data` | Verify seed data files exist |
| `discover-free-models` | List all free model candidates and availability |
| `calibrate-free-models` | Rank free models on calibration tasks |
| `run-episode` | Run one task episode |
| `run-benchmark` | Run full benchmark, print metrics |
| `benchmark-free-models` | Benchmark all available free models |
| `inspect-task` | Show task details |
| `analyze-failures` | Categorize failure modes |

---

## Project Structure

```
tau-free-bench/
  data/
    retail/          # 10 users, 12 products, 20 orders, 10 tasks, policy
    airline/         # smaller airline domain
  src/taufreebench/
    core/            # types, DB, tool registry, environment, evaluator, metrics
    domains/         # retail and airline tools + seed data
    users/           # scripted, Ollama, Gemini, Groq, OpenRouter users
    agents/          # rule-based, Ollama, Gemini, Groq, OpenRouter, ReAct agents
    providers/       # provider abstractions, model discovery, calibration
    runners/         # episode runner, benchmark runner, failure analyzer
    cli.py           # Typer CLI
  tests/             # pytest tests (no network calls)
  docs/              # architecture and adding domains
```

---

## Running Tests

```bash
pytest tests/ -v
```

All tests run without any API keys or Ollama. Network is never called in tests.

---

## Adding Domains

See [docs/adding_domains.md](docs/adding_domains.md).

---

## Adding Providers

See [docs/free_models.md](docs/free_models.md).
