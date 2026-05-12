# Benchmark Report — 20260512_120058

> **VALIDITY: Deterministic sanity check. Not comparable to τ-bench paper results because this run uses a rule-based agent and scripted user. Do NOT compare these scores to the paper's GPT-4o results.**

> This project is an educational, clean-room, mini τ-bench-style benchmark. It is not the original τ-bench and its scores are not directly comparable to the paper.

## Run Metadata

| Field | Value |
|---|---|
| Generated | 2026-05-12T12:00:58 |
| Git commit | `4fda3a5` |
| Dataset hash | `d2acc854d462` |
| Domain | `retail` |
| Task count | 25 |
| Trials per task | 3 |
| k values | [1, 2, 3] |
| Agent | `rule` |
| User simulator | `scripted` |
| Validity mode | `deterministic_sanity_check` |

## Aggregate Metrics

- **pass^1**: 1.000
- **pass^2**: 1.000
- **pass^3**: 1.000
- **pass@1**: 1.000
- **pass@2**: 1.000
- **pass@3**: 1.000
- Avg turns: 7.60
- Avg tool calls: 3.20
- Invalid tool call rate: 0.000
- Max-turn failure rate: 0.000
- Tool-error rate: 0.000
- Mean latency: 0.00s

## Per-Task Results

| task_id | tags | successes/trials | pass^1 | avg_turns | failure_class | diff_summary |
|---|---|---|---|---|---|---|
| retail_task_001 | cancel,pending,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_002 | return,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_003 | exchange,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_004 | modify,pending,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_005 | modify,auth | 3/3 | 1.00 | 6.0 | — | — |
| retail_task_006 | modify,pending,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_007 | compound,cancel,modify,auth | 3/3 | 1.00 | 11.0 | — | — |
| retail_task_008 | policy,auth | 3/3 | 1.00 | 6.0 | — | — |
| retail_task_009 | calculation,auth | 3/3 | 1.00 | 11.0 | — | — |
| retail_task_010 | exchange,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_011 | return,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_012 | cancel,pending,auth | 3/3 | 1.00 | 9.0 | — | — |
| retail_task_013 | modify,pending,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_014 | modify,pending,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_015 | return,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_016 | return,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_017 | exchange,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_018 | policy,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_019 | policy,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_020 | return,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_021 | read_only,auth | 3/3 | 1.00 | 5.0 | — | — |
| retail_task_022 | compound,cancel,modify,auth | 3/3 | 1.00 | 11.0 | — | — |
| retail_task_023 | compound,modify,auth | 3/3 | 1.00 | 12.0 | — | — |
| retail_task_024 | return,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |
| retail_task_025 | exchange,delivered,auth | 3/3 | 1.00 | 7.0 | — | — |

## Top 5 Easiest Tasks

- `retail_task_001` — pass^1 = 1.00 (3/3)
- `retail_task_002` — pass^1 = 1.00 (3/3)
- `retail_task_003` — pass^1 = 1.00 (3/3)
- `retail_task_004` — pass^1 = 1.00 (3/3)
- `retail_task_005` — pass^1 = 1.00 (3/3)

## Top 5 Hardest Tasks

- `retail_task_001` — pass^1 = 1.00 (3/3)
- `retail_task_002` — pass^1 = 1.00 (3/3)
- `retail_task_003` — pass^1 = 1.00 (3/3)
- `retail_task_004` — pass^1 = 1.00 (3/3)
- `retail_task_005` — pass^1 = 1.00 (3/3)

## Example Successful Trajectories

### `retail_task_001` — ✅ reward=1 failure_class=success

Trajectory (truncated):

```
USER : Hi, I'd like to cancel my order #W4082615 because I ordered it by mistake.
AGENT: Hello! I'm happy to help. Could you please verify your identity? I'll need your email address or your full name and ZIP code.
USER : My email is mei.patel@example.com.
TOOL→ find_user_id_by_email({"email": "mei.patel@example.com"})
RESLT: mei_patel_7272
AGENT: I've verified your identity. How can I help you today?
USER : I need to cancel order #W4082615. The reason is that I ordered it by mistake.
TOOL→ get_order_details({"order_id": "#W4082615"})
RESLT: {'order_id': '#W4082615', 'user_id': 'mei_patel_7272', 'status': 'pending', 'items': [{'item_id': 'item_tshirt_m_blue', 'product_id': 'prod_tshirt_001', 'name':
AGENT: I'll cancel order #W4082615 with reason 'ordered by mistake'. Shall I proceed?
USER : Yes, please go ahead and cancel it.
TOOL→ cancel_pending_order({"order_id": "#W4082615", "reason": "ordered by mistake"})
RESLT: {'order_id': '#W4082615', 'status': 'cancelled', 'cancellation_reason': 'ordered by mistake'}
AGENT: Order #W4082615 has been successfully cancelled. Is there anything else I can help you with?
USER : ###STOP###
```

### `retail_task_002` — ✅ reward=1 failure_class=success

Trajectory (truncated):

```
USER : Hello, I'd like to return the jeans from my delivered order #W7382910.
AGENT: Hello! I'm happy to help. Could you please verify your identity? I'll need your email address or your full name and ZIP code.
USER : My email is yusuf.rossi@example.com.
TOOL→ find_user_id_by_email({"email": "yusuf.rossi@example.com"})
RESLT: yusuf_rossi_9620
AGENT: I've verified your identity. How can I help you today?
USER : I want to return the item in order #W7382910 and refund to credit_card_5421098.
TOOL→ get_order_details({"order_id": "#W7382910"})
RESLT: {'order_id': '#W7382910', 'user_id': 'yusuf_rossi_9620', 'status': 'delivered', 'items': [{'item_id': 'item_jeans_30_dark', 'product_id': 'prod_jeans_002', 'nam
AGENT: I'll process a return for order #W7382910. The refund will go to payment method credit_card_5421098. Shall I proceed?
USER : Yes, please process the return.
TOOL→ return_delivered_order_items({"order_id": "#W7382910", "item_ids": ["item_jeans_30_dark"], "payment_method_id": "credit_card_5421)
RESLT: {'order_id': '#W7382910', 'status': 'return requested', 'return_items': ['item_jeans_30_dark'], 'refund_amount': 49.99, 'payment_method_id': 'credit_card_542109
AGENT: Your return has been requested. You will receive a refund of $49.99.
USER : ###STOP###
```

### `retail_task_003` — ✅ reward=1 failure_class=success

Trajectory (truncated):

```
USER : Hi, I want to exchange the t-shirt in order #W1937482. I have item_tshirt_s_red and want item_tshirt_m_blue instead.
AGENT: Hello! I'm happy to help. Could you please verify your identity? I'll need your email address or your full name and ZIP code.
USER : My email is sofia.chen@example.com.
TOOL→ find_user_id_by_email({"email": "sofia.chen@example.com"})
RESLT: sofia_chen_3415
AGENT: I've verified your identity. How can I help you today?
USER : Exchange item_tshirt_s_red for item_tshirt_m_blue in order #W1937482. Use credit_card_3847291 for payment.
TOOL→ get_order_details({"order_id": "#W1937482"})
RESLT: {'order_id': '#W1937482', 'user_id': 'sofia_chen_3415', 'status': 'delivered', 'items': [{'item_id': 'item_tshirt_s_red', 'product_id': 'prod_tshirt_001', 'name
AGENT: I'll exchange the items in order #W1937482. Shall I proceed?
USER : Yes, please proceed with the exchange.
TOOL→ exchange_delivered_order_items({"order_id": "#W1937482", "item_ids": ["item_tshirt_s_red"], "new_item_ids": ["item_tshirt_m_blue"],)
RESLT: {'order_id': '#W1937482', 'status': 'exchange requested', 'exchange_items': ['item_tshirt_s_red'], 'exchange_new_items': ['item_tshirt_m_blue'], 'exchange_price
AGENT: Your exchange has been requested.
USER : ###STOP###
```

## Paper-Comparability

| Criterion | This Run |
|---|---|
| LLM agent used | **no** (rule-based) |
| LLM user used | **no** (scripted) |
| Strict DB-state evaluator | yes |
| No LLM judge | yes |
| Custom/mini dataset | yes (not original τ-bench) |
| Task count | 25 (original τ-retail: 115) |
| Trials | 3 |
| pass^k implemented | yes |
| pass@k implemented | yes |

**Verdict**: ❌ NOT paper-comparable. Rule-based agent + scripted user = deterministic sanity check only.

_Original τ-bench paper (Yao et al. 2024) used GPT-4o and Claude-3.5 on the full τ-retail (115 tasks) and τ-airline (128 tasks) datasets with LLM-simulated users. This repo uses a custom 25-task mini dataset and is NOT a reproduction of the paper._
