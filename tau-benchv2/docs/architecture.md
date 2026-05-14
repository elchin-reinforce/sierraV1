# Architecture

## Episode Loop

```
Task loaded → DB deep-copied → User initialized → Agent initialized
                    ↓
             User sends opening message
                    ↓
              ┌─────────────────────────────┐
              │  Agent acts (≤1 tool OR 1 msg)│
              └─────────┬───────────────────┘
                        │
          ┌─────────────┴──────────────┐
          │ ToolCall                    │ AgentMessage
          ▼                            ▼
  Execute tool on DB            User responds
  Return observation            If ###STOP### → end
  Add to agent history          Add to both histories
          └─────────────┬──────────────┘
                        ▼
                 Next turn (max_turns)
                        ↓
               Evaluate: expected_db vs final_db
```

## Evaluation

1. Deep-copy `initial_db`
2. Replay `task.expected_actions` on the copy → `expected_db`
3. `action_reward = 1` if `expected_db == final_db` (after diff)
4. `output_reward = 1` if all `required_outputs` appear in agent messages
5. `reward = action_reward * output_reward`

## Key Design Principles

- **Deterministic scoring**: no LLM judge
- **DB state comparison**: robust to equivalent action orderings
- **Deep copy**: initial DB never mutated between episodes
- **Free-first**: works with zero API keys (rule-based agent + scripted user)
