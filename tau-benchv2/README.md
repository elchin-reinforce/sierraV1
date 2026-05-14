# Sierra V2 — τ²-Bench-Style Dual-Control Agent Benchmark

> **Sierra V2 is a clean-room educational τ²-bench-style benchmark. It is not the original τ²-bench and its scores are not directly comparable to the paper.**

A dual-control benchmark for LLM customer-support agents. Both the agent and the simulated user have tools that affect a shared environment (telecom backend + phone device). The agent must coordinate with the user to resolve technical-support tickets.

Paper reference: *τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment*.

---

## V1 vs V2

Two separate projects. V1 stays at `/Users/hasanov/tau-free-bench/` (parent). V2 lives at `/Users/hasanov/tau-free-bench/tau-benchv2/` (this folder).

### Sierra V1 — τ-bench-style (single-control)

| Aspect | V1 |
|---|---|
| Domain | Retail (orders, returns, exchanges, address changes) |
| Who has tools | Agent only |
| Who controls state | Agent only |
| User simulator | Talks only |
| Evaluation | Final DB-state exact-match + required output substrings |
| Tasks | 25 |
| Benchmark modes | rule+scripted (sanity) / LLM+scripted (Mode 2) / LLM+LLM (Mode 3) |
| Best score observed | claude-opus-4-7: pass^1 = 0.747, pass@3 = 1.000 (user sim: gpt-4-0613 @ T=1.0) |

### Sierra V2 — τ²-bench-style (dual-control)

| Aspect | V2 |
|---|---|
| Domain | Telecom support (phone/device troubleshooting) |
| Who has tools | **Agent AND user** |
| Who controls state | **Both** — agent owns backend DB, user owns device DB |
| User simulator | Talks + calls user-side tools (status bar, toggle airplane, reseat SIM, reboot, etc.) |
| Evaluation | **Assertion-based** (`assert_service_connected`, `assert_can_send_mms`, ...) + required outputs |
| Tasks | 60 (compositional: 1–4 atomic subtasks each) |
| Issue types | service_issue, mobile_data_issue, mms_issue (20 each) |
| Personas | none / easy / hard (20 each) |
| Benchmark modes | **default** (dual) / **no-user** (agent has both tool sets) / **oracle-plan** (agent given ground-truth plan) |
| Tools | 19 agent backend + 30 user device + 13 assertions |

---

## Architecture

```
                  ┌─────────────────────┐
   agent_db ◄────►│  AGENT TOOLS (19)   │
   (lines, plans, │  find_customer_*    │
    bills,        │  make_payment       │
    customers)    │  resume_line, etc.  │
                  └──────────▲──────────┘
                             │
        ┌─── messages (visible to both) ────┐
        │                                   │
     ┌──┴──┐                             ┌──┴──┐
     │AGENT│─── only sees its own ─►─────│USER │
     └──┬──┘    tool outputs             └──┬──┘
        │                                   │
        └─── only sees its own ────────────┐│
             tool outputs                  ││
                                          ▼▼
                  ┌─────────────────────┐
   user_device_db│  USER TOOLS (30)    │
   (airplane,    │  toggle_airplane    │
    sim, apn,    │  check_status_bar   │
    mms, vpn,    │  reseat_sim, reboot │
    signal, ...) │  send_test_mms, ... │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  ASSERTIONS (13)    │  →  pass^k / pass@k
                  └─────────────────────┘
```

---

## Setup

```bash
cd tau-benchv2
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic typer rich python-dotenv httpx anthropic openai \
            groq google-generativeai eval_type_backport
```

Copy `.env.example` to `.env` and add keys for the providers you want:

```
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
```

---

## Quick Start

```bash
# Sanity check (no LLM needed):
PYTHONPATH=src python -m taufreebench.cli telecom-stats
PYTHONPATH=src python -m taufreebench.cli validate-dual-dataset --domain telecom
PYTHONPATH=src python -m taufreebench.cli report-dual-results \
  --domain telecom --mode default --agent rule --user scripted --trials 1 --k 1

# Paper-style LLM benchmark (free, local):
ollama pull qwen3:8b && ollama pull llama3.1:8b
PYTHONPATH=src python -m taufreebench.cli report-dual-results \
  --domain telecom --mode default \
  --agent ollama --agent-model qwen3:8b \
  --user ollama --user-model llama3.1:8b \
  --trials 4 --k 1 --k 2 --k 3 --k 4

# Paper-style LLM benchmark (paid, hosted):
PYTHONPATH=src python -m taufreebench.cli report-dual-results \
  --domain telecom --mode default \
  --agent openai --agent-model gpt-5.5 \
  --user openai --user-model gpt-4-0613 \
  --trials 1 --k 1

# Three-mode ablation (default / no-user / oracle-plan):
PYTHONPATH=src python -m taufreebench.cli compare-dual-modes \
  --domain telecom \
  --agent openai --agent-model gpt-5.5 \
  --user openai --user-model gpt-4-0613 \
  --trials 1
```

---

## Results

**Setup for LLM rows below:**
- 60 telecom tasks × 3 trials = 180 episodes per model
- **Mode 3 — default (dual-control, LLM agent + LLM user)**
- User simulator: `gpt-4-0613` at temperature 1.0 (paper standard)
- Agent: temperature 0.0 where supported. gpt-5.5, claude-opus-4-7, and claude-sonnet-4-5-20250929 don't accept `temperature` (reasoning models / deprecated param) — they use the API's default.

| Agent | User sim | pass^1 | pass^2 | pass^3 | pass@1 | pass@2 | pass@3 | Run |
|-------|----------|-------:|-------:|-------:|-------:|-------:|-------:|-----|
| gpt-5.4-mini | gpt-4-0613 (T=1.0) | **0.067** | 0.056 | 0.050 | 0.067 | 0.078 | **0.083** | [20260513_191731](runs/20260513_191731/report.md) |
| claude-sonnet-4-5 | gpt-4-0613 (T=1.0) | 0.056 | 0.044 | 0.033 | 0.056 | 0.067 | 0.067 | [20260513_194830](runs/20260513_194830/report.md) |
| claude-opus-4-7 | gpt-4-0613 (T=1.0) | 0.050 | 0.033 | 0.033 | 0.050 | 0.067 | 0.083 | [20260513_191931](runs/20260513_191931/report.md) |
| gpt-5.5 | gpt-4-0613 (T=1.0) | 0.044 | 0.039 | 0.033 | 0.044 | 0.050 | 0.050 | [20260513_195801](runs/20260513_195801/report.md) |
| Sanity: rule + scripted | scripted | 0.550 | — | — | 0.550 | — | — | [20260513_110328](runs/20260513_110328/report.md) |

**⚠️ Known V2 limitation — all LLM scores are very low.** The dominant failure mode (~40–55% of episodes per model) is the LLM user simulator emitting `###TRANSFER###` (give up / transfer to human) before the agent has resolved the issue. The LLM agents make only 1.8–3.9 backend tool calls per episode and the LLM users only 1.9–3.4 device tool calls — both sides under-using their tools. The rule+scripted baseline scores 0.550 only because the scripted user mechanically executes the task's solution actions regardless of agent input; it does not represent a meaningful LLM result.

This is a **dual-control coordination problem** rather than a model-capability problem. V2 needs prompt tuning of the user simulator (less eager transfer), better agent prompting for the dual-control flow, and possibly a "soft transfer" mechanism. Treat the current V2 scores as a baseline showing the **dual-control gap** between V1 (single-control, all models near saturation) and V2 (dual-control, all models struggle).

*Note: the original ask referenced "Sonnet 3.5", which Anthropic has retired. Substituted with `claude-sonnet-4-5-20250929`, the closest current Sonnet-tier model.*

---

## CLI Commands

| Command | Purpose |
|---------|---------|
| `seed-telecom-data` | Verify telecom seed DBs exist |
| `generate-telecom-tasks --count 60` | Generate compositional tasks from atomic subtasks |
| `validate-dual-dataset --domain telecom` | Replay all task solutions; assertions must flip FAIL→PASS |
| `telecom-stats` | DB and task statistics |
| `run-dual-episode --task ... --mode ... --agent ... --user ...` | Run a single episode |
| `report-dual-results ...` | Full benchmark + report saved to `runs/<timestamp>/` |
| `compare-dual-modes ...` | All 3 modes side-by-side |
| `audit-tau2-validity --run runs/<ts>` | τ²-bench paper-validity checklist for a saved run |

V1 retail commands (`seed-data`, `report-results`, ...) are preserved.

---

## Honest Description

> "Built Sierra V2, a clean-room τ²-bench-style dual-control benchmark for LLM customer-support agents. Added user-side tools, mocked device state, telecom troubleshooting workflows, assertion-based evaluation, pass^k/pass@k metrics, and default/no-user/oracle-plan ablations to diagnose reasoning vs coordination failures."

---

## Limitations

- Not the original τ²-bench. Smaller synthetic dataset (60 tasks).
- Results depend on user-simulator quality. gpt-4-0613 @ T=1.0 is the paper's choice; other user sims give different absolute numbers.
- Local Ollama model performance varies by hardware and model version.
- Device state is mocked — no actual phone interaction.

---

## Project Structure

```
tau-benchv2/
  data/telecom/
    agent_db.json           # 30 customers, 50 lines, 10 plans, 40 bills
    user_device_db.json     # 50 devices
    tasks.json              # 60 compositional tasks
    policy.md
    user_personas.json
  src/taufreebench/
    core/
      dual_environment.py   # Dual-control loop
      dual_evaluator.py     # Assertion-based evaluation
      types.py              # DualToolCall, DualEpisodeResult, TelecomTask
    domains/telecom/
      agent_tools.py        # 19 backend tools
      user_tools.py         # 30 device tools
      assertions.py         # 13 assertion functions
      scenarios.py          # 16 atomic subtasks
      task_generator.py     # Compositional task generator
    agents/                 # rule_based_telecom_agent, {ollama,openai,anthropic}_dual_tool_agent
    users/                  # scripted_dual_user, {ollama,openai,anthropic}_dual_user
    runners/                # run_dual_episode, run_dual_benchmark, dual_report
    cli.py
  runs/                     # generated benchmark reports
```
