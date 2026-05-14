# Benchmark Report — 20260512_125207

> **VALIDITY: Partial LLM benchmark. Tests LLM agent tool-use and policy-following, but the user is scripted, so interaction is not fully paper-style. Scores are not directly comparable to the τ-bench paper.**

> This project is an educational, clean-room, mini τ-bench-style benchmark. It is not the original τ-bench and its scores are not directly comparable to the paper.

## Run Metadata

| Field | Value |
|---|---|
| Generated | 2026-05-12T12:52:07 |
| Git commit | `3eb55dd` |
| Dataset hash | `d2acc854d462` |
| Domain | `retail` |
| Task count | 25 |
| Trials per task | 3 |
| k values | [1, 2, 3] |
| Agent | `groq` |
| User simulator | `scripted` |
| Validity mode | `partial_llm_benchmark` |

## Aggregate Metrics

- **pass^1**: 0.000
- **pass^2**: 0.000
- **pass^3**: 0.000
- **pass@1**: 0.000
- **pass@2**: 0.000
- **pass@3**: 0.000
- Avg turns: 0.00
- Avg tool calls: 0.00
- Invalid tool call rate: 0.000
- Max-turn failure rate: 0.000
- Tool-error rate: 0.000

## Failure Breakdown

| failure_class | count |
|---|---|
| wrong_database_state_and_missing_output | 75 |

## Per-Task Results

| task_id | tags | successes/trials | pass^1 | avg_turns | failure_class | diff_summary |
|---|---|---|---|---|---|---|
| retail_task_001 | cancel,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_002 | return,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_003 | exchange,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_004 | modify,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_005 | modify,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_006 | modify,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_007 | compound,cancel,modify,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_008 | policy,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_009 | calculation,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_010 | exchange,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_011 | return,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_012 | cancel,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_013 | modify,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_014 | modify,pending,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_015 | return,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_016 | return,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_017 | exchange,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_018 | policy,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_019 | policy,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_020 | return,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_021 | read_only,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_022 | compound,cancel,modify,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_023 | compound,modify,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_024 | return,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |
| retail_task_025 | exchange,delivered,auth | 0/3 | 0.00 | 0.0 | wrong_database_state_and_missing_output | — |

## Top 5 Hardest Tasks

- `retail_task_001` — pass^1 = 0.00 (0/3)
- `retail_task_002` — pass^1 = 0.00 (0/3)
- `retail_task_003` — pass^1 = 0.00 (0/3)
- `retail_task_004` — pass^1 = 0.00 (0/3)
- `retail_task_005` — pass^1 = 0.00 (0/3)

## Example Failed Trajectories

### `retail_task_001` — ❌ reward=0 failure_class=wrong_database_state_and_missing_output

Trajectory (truncated):

```
```

### `retail_task_002` — ❌ reward=0 failure_class=wrong_database_state_and_missing_output

Trajectory (truncated):

```
```

### `retail_task_003` — ❌ reward=0 failure_class=wrong_database_state_and_missing_output

Trajectory (truncated):

```
```

## Paper-Comparability

| Criterion | This Run |
|---|---|
| LLM agent used | yes |
| LLM user used | **no** (scripted) |
| Strict DB-state evaluator | yes |
| No LLM judge | yes |
| Custom/mini dataset | yes (not original τ-bench) |
| Task count | 25 (original τ-retail: 115) |
| Trials | 3 |
| pass^k implemented | yes |
| pass@k implemented | yes |

**Verdict**: ⚠️ PARTIALLY comparable. LLM agent tested, but scripted user differs from paper's LLM user.

_Original τ-bench paper (Yao et al. 2024) used GPT-4o and Claude-3.5 on the full τ-retail (115 tasks) and τ-airline (128 tasks) datasets with LLM-simulated users. This repo uses a custom 25-task mini dataset and is NOT a reproduction of the paper._
