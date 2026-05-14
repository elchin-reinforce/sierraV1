# Sierra V2 Dual-Control Benchmark Report — 20260513_110328

> **Sierra V2 Dual-Control Benchmark Report — mini τ²-bench-style, NOT original τ²-bench, scores not comparable to paper.**

> VALIDITY: Sierra V2 dual-control deterministic sanity check. Rule-based agent + scripted user. Not comparable to τ²-bench paper.

## Run Metadata

| Field | Value |
|---|---|
| Generated | 2026-05-13T11:03:28 |
| Git commit | `0fc0317` |
| Dataset hash | `f5cf91d78484` |
| Domain | `telecom` |
| Mode | `default` |
| Agent | `rule` |
| User simulator | `scripted` |
| Trials per task | 1 |
| k values | [1] |
| Total tasks | 60 |
| Issue types | mms_issue=20, mobile_data_issue=20, service_issue=20 |
| Personas | easy=20, hard=20, none=20 |
| Validity mode | `dual_sanity_check` |

## Aggregate Metrics

- **pass^1**: 0.550
- **pass@1**: 0.550
- Avg turns: 3.83
- Avg agent tool calls: 0.00
- Avg user tool calls: 1.88
- Invalid agent tool rate: 0.000
- Invalid user tool rate: 0.000
- Agent tool-error rate: 0.000
- User tool-error rate: 0.000
- Max-turn failure rate: 0.000
- Assertion failure rate: 0.450
- Output failure rate: 0.000
- Mean latency: 0.00s

## Breakdown by Issue Type

| issue_type | tasks | pass^1 | pass@1 |
|---|---|---|---|
| mms_issue | 20 | 0.800 | 0.800 |
| mobile_data_issue | 20 | 0.550 | 0.550 |
| service_issue | 20 | 0.300 | 0.300 |

## Breakdown by Persona

| persona | tasks | pass^1 | pass@1 |
|---|---|---|---|
| easy | 20 | 0.650 | 0.650 |
| hard | 20 | 0.600 | 0.600 |
| none | 20 | 0.400 | 0.400 |

## Breakdown by Subtask Count

| n_subtasks | tasks | pass^1 |
|---|---|---|
| 1 | 24 | 0.833 |
| 2 | 26 | 0.346 |
| 3 | 8 | 0.375 |
| 4 | 2 | 0.500 |

## Failure Breakdown

| failure_class | count |
|---|---|
| assertion_failed | 27 |

## Top 5 Easiest Tasks

- `telecom_002` — pass^1 = 1.00 (1/1)
- `telecom_003` — pass^1 = 1.00 (1/1)
- `telecom_005` — pass^1 = 1.00 (1/1)
- `telecom_008` — pass^1 = 1.00 (1/1)
- `telecom_011` — pass^1 = 1.00 (1/1)

## Top 5 Hardest Tasks

- `telecom_001` — pass^1 = 0.00 (0/1)
- `telecom_004` — pass^1 = 0.00 (0/1)
- `telecom_006` — pass^1 = 0.00 (0/1)
- `telecom_007` — pass^1 = 0.00 (0/1)
- `telecom_009` — pass^1 = 0.00 (0/1)

## Example Successful Trajectories

### `telecom_002` — PASS reward=1 failure_class=success mode=default

Assertions: 1/1 passing.

Trajectory (truncated):

```
USER  : Hi, my phone has no service. Can you help?
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
U→TOOL: reseat_sim_card({"device_id": "device_024"})
U→TOOL: reseat_sim_card({"device_id": "device_024"})
  ↳   : {'device_id': 'device_024', 'sim_inserted': True, 'sim_status': 'valid'}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : Looks good, all working now. ###STOP###
```

### `telecom_003` — PASS reward=1 failure_class=success mode=default

Assertions: 2/2 passing.

Trajectory (truncated):

```
USER  : Hi, I can't send picture messages.
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
U→TOOL: toggle_mobile_data({"device_id": "device_040", "enabled": true})
U→TOOL: toggle_mobile_data({"device_id": "device_040", "enabled": true})
  ↳   : {'device_id': 'device_040', 'mobile_data_enabled': True}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : OK, done.
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
U→TOOL: grant_app_permission({"device_id": "device_040", "app_name": "messages", "permission": "mms"})
U→TOOL: grant_app_permission({"device_id": "device_040", "app_name": "messages", "permission": "mms"})
  ↳   : {'device_id': 'device_040', 'app_name': 'messages', 'permission': 'mms', 'granted': True}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : Looks good, all working now. ###STOP###
```

### `telecom_005` — PASS reward=1 failure_class=success mode=default

Assertions: 3/3 passing.

Trajectory (truncated):

```
USER  : Hi, my mobile data is really slow today.
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
U→TOOL: toggle_device_roaming({"device_id": "device_027", "enabled": true})
U→TOOL: toggle_device_roaming({"device_id": "device_027", "enabled": true})
  ↳   : {'device_id': 'device_027', 'device_roaming_enabled': True}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : OK, done.
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
U→TOOL: switch_network_mode({"device_id": "device_027", "network_type": "4G"})
U→TOOL: switch_network_mode({"device_id": "device_027", "network_type": "4G"})
  ↳   : {'device_id': 'device_027', 'network_type': '4G'}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : Looks good, all working now. ###STOP###
```

## Example Failed Trajectories

### `telecom_001` — FAIL reward=0 failure_class=assertion_failed mode=default

Assertions: 0/3 passing.

Failing assertions:
- `assert_line_active` — line.status is suspended
- `assert_bill_paid` — bill.status is overdue
- `assert_service_connected` — line.status is suspended

Trajectory (truncated):

```
USER  : Hi, my phone has no service. Can you help?
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
USER  : Looks good, all working now. ###STOP###
```

### `telecom_004` — FAIL reward=0 failure_class=assertion_failed mode=default

Assertions: 0/4 passing.

Failing assertions:
- `assert_service_connected` — line.status is suspended
- `assert_line_active` — line.status is suspended
- `assert_bill_paid` — bill.status is overdue
- `assert_service_connected` — line.status is suspended

Trajectory (truncated):

```
USER  : Hi, my phone has no service. Can you help?
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
U→TOOL: toggle_airplane_mode({"device_id": "device_012", "enabled": false})
U→TOOL: toggle_airplane_mode({"device_id": "device_012", "enabled": false})
  ↳   : {'device_id': 'device_012', 'airplane_mode': False}
AGENT : I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.
USER  : Looks good, all working now. ###STOP###
```

### `telecom_006` — FAIL reward=0 failure_class=assertion_failed mode=default

Assertions: 0/1 passing.

Failing assertions:
- `assert_mobile_data_working` — data limit exceeded

Trajectory (truncated):

```
USER  : Hi, my mobile data is really slow today.
AGENT : Hello, this is telecom support. May I have the phone number on the account so I can look you up?
USER  : Looks good, all working now. ###STOP###
```

## Paper-Comparability (τ²-bench)

| Criterion | This Run | τ²-bench Paper |
|---|---|---|
| Dual-control (agent + user with tools) | yes | yes |
| LLM agent | **no** (rule-based) | yes (GPT-4o / Claude-3.5) |
| LLM user with tools | **no** (scripted) | yes |
| Assertion-based evaluation | yes | yes |
| No LLM judge | yes | yes |
| Dataset | custom 60-task mini (this repo) | original τ²-bench (telecom: ~114) |
| Task count | 60 | ~114 (telecom) |
| Trials | 1 | typically 4-5 |
| pass^k / pass@k | yes | pass^k |

**Verdict**: NOT paper-comparable. Rule-based agent + scripted user = deterministic sanity check only.

_Original τ²-bench (Sierra/Yao 2025) uses a dual-control setup with an LLM agent, an LLM user simulator, and a much larger curated task set. This repo is a clean-room educational mini reimplementation; scores are NOT directly comparable to the paper._
