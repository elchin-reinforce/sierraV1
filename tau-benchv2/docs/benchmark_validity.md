# Benchmark Validity Guide

> **This project is an educational, clean-room, mini τ-bench-style benchmark. It is not the original τ-bench and its scores are not directly comparable to the paper.**

---

## The 4 Benchmark Modes

### Mode 1 — Rule-based agent + Scripted user (deterministic sanity check)

```bash
python -m taufreebench.cli report-results \
  --domain retail --agent rule --user scripted --trials 3 --k 1 --k 2 --k 3
```

| Property | Value |
|---|---|
| Agent | Rule-based state machine (no LLM) |
| User | Pre-scripted turns from tasks.json |
| Randomness | None — fully deterministic |
| Purpose | Verify the benchmark pipeline and dataset integrity |
| Comparable to τ-bench paper? | **No** |

**When to use**: CI/CD, debugging, confirming tools and evaluator work correctly. The 92% rule-based pass rate is NOT a meaningful LLM benchmark result — it measures whether the state machine correctly interprets the scripted conversation.

---

### Mode 2 — LLM agent + Scripted user (partial LLM benchmark)

```bash
python -m taufreebench.cli report-results \
  --domain retail --agent ollama --agent-model qwen3:8b \
  --user scripted --trials 3 --k 1 --k 2 --k 3
```

| Property | Value |
|---|---|
| Agent | LLM (Ollama/Groq/Gemini/OpenRouter) |
| User | Pre-scripted turns from tasks.json |
| Randomness | Agent introduces LLM stochasticity |
| Purpose | Test LLM tool-use and policy-following with controlled user |
| Comparable to τ-bench paper? | **Partially** — agent is LLM, but user is scripted |

**When to use**: Comparing LLM agents against each other on the same fixed conversation scripts. Scores are repeatable across user turns but do not reflect realistic user behavior.

---

### Mode 3 — LLM agent + LLM user (mini paper-style benchmark)

```bash
python -m taufreebench.cli report-results \
  --domain retail \
  --agent ollama --agent-model qwen3:8b \
  --user ollama --user-model llama3.1:8b \
  --trials 3 --k 1 --k 2 --k 3
```

| Property | Value |
|---|---|
| Agent | LLM (any provider) |
| User | LLM-simulated (any provider) |
| Randomness | Both agent and user are stochastic |
| Purpose | Closest mini version of τ-bench interaction loop |
| Comparable to τ-bench paper? | **Closest in this repo, but still custom/smaller** |

**When to use**: End-to-end evaluation closest to the paper's methodology. Use multiple trials (≥3) and report pass^k and pass@k. Results are still not directly comparable to the paper because the dataset is smaller and custom.

---

### Mode 4 — Benchmark all available free models

```bash
python -m taufreebench.cli benchmark-free-models \
  --domain retail --user scripted --trials 2 --k 1 --k 2
```

| Property | Value |
|---|---|
| Agent | All available free/local LLMs |
| User | Scripted (for reproducibility) |
| Purpose | Rank free models on this mini benchmark |
| Comparable to τ-bench paper? | **No direct comparison, but useful for model ranking** |

---

## Important Warnings

1. **Do not compare rule/scripted scores to paper scores.** The τ-bench paper reports GPT-4o scores of ~0.69 (τ-retail) on 115 tasks. A rule-based agent scoring 0.92 on 25 tasks is not comparable.

2. **Dataset is smaller and synthetic.** This repo uses a 25-task custom dataset, not the original 115-task τ-retail or 128-task τ-airline datasets.

3. **Scripted user scores are easier than LLM-user scores.** The scripted user always provides the right information at the right time, making tasks easier than realistic LLM-user interaction.

4. **Free model results may vary.** Ollama models change between versions, and API-hosted models change over time.

5. **Generated reports include git commit hash and dataset hash.** Always check these when comparing runs.

---

## What pass^k and pass@k Mean

- **pass^k** (consistency): Expected fraction of all k-subsets of trials where ALL succeed. Measures reliability.
  - pass^1 = fraction of single trials that succeed
  - pass^2 on 3 trials = fraction of trial-pairs where both succeed
  
- **pass@k** (capability): Probability that at least one of k random attempts succeeds. Measures raw capability.
  - pass@1 = same as pass^1
  - pass@k ≥ pass^k always

For the paper's methodology, pass^1 is the primary metric reported as the benchmark score.

---

## How to Describe This Project Honestly

When writing about results from this benchmark, use language like:

> "We evaluated [model] on a custom mini τ-bench-style retail benchmark (25 tasks, [N] trials). Results are not directly comparable to the original τ-bench paper. The benchmark uses the same evaluation methodology (DB-state comparison, pass^k metrics) but a smaller, custom dataset."

Do NOT write:
- "We reproduced τ-bench" (you didn't — different dataset)
- "Our model scores X on τ-bench" (this is not τ-bench)
- "This is better than GPT-4o on τ-bench" (different dataset, not comparable)

---

## Paper Reference

The original τ-bench paper:
> Shunyu Yao, Noah Shinn, Pedram Razavi, Karthik Narasimhan. "τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains." arXiv 2024.

This repository is an independent educational reimplementation. It is not affiliated with the original paper authors.
