# τ²-bench Validity Audit — telecom / mode=default

This is a clean-room educational mini τ²-bench-style benchmark. It is **not** the original τ²-bench and its scores are not directly comparable to the paper.

## A. Environment Loop

| Check | Status | Notes |
|---|---|---|
| Agent sees policy, conversation, agent-tool results | PASS | by design |
| Agent does NOT see user-side tool calls/results | PASS | trajectory `visible_to_*` flags |
| User has its own tool set and DB view | PASS | dual-control |
| Agent and user mutate JSON DBs via tools only | PASS | by design |
| Mode used | `default` | one of {default, no_user, oracle_plan} |

## B. Evaluation

| Check | Status | Notes |
|---|---|---|
| Outcome judged by post-state assertions | PASS | `run_assertions` over final dbs |
| Required-output substring check | PASS | case-insensitive substring match |
| No LLM judge used | PASS | deterministic |
| pass^k implemented | PASS | k=[1, 2, 3] |
| pass@k implemented | PASS | k=[1, 2, 3] |
| Failure classification | PASS | success / assertion_failed / max_turns_exceeded / invalid_*_tool_call / *_tool_error / missing_required_output / incomplete_troubleshooting / ... |

## C. Comparability to τ²-bench Paper

| Criterion | This Run | τ²-bench Paper |
|---|---|---|
| LLM agent | yes | yes |
| LLM user with tools | yes | yes |
| Telecom task count | 60 | ~114 |
| Trials | 3 | typically 4-5 |
| Dataset | custom mini (this repo) | original τ²-bench |
| Git commit | `a557473` | — |
| Dataset hash | `f5cf91d78484` | — |
| Validity mode | `dual_mini_paper_style` | — |

**Verdict**: CLOSEST to paper-style in this repo (LLM agent + LLM user, both with tools). Still custom/smaller dataset — not original τ²-bench.
