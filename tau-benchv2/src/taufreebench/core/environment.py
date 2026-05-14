"""Benchmark environment: orchestrates user ↔ agent ↔ tool loop."""
from __future__ import annotations
import time
from typing import Any

from .types import (
    Task, EpisodeResult, TrajectoryStep, ToolCall, AgentMessage,
    ToolResult, UserMessage,
)
from .tool import ToolDefinition
from .db import deep_copy_db
from .evaluator import evaluate_episode


class BenchmarkEnvironment:
    def __init__(
        self,
        domain_name: str,
        db: dict[str, Any],
        tools: dict[str, ToolDefinition],
        policy: str,
        task: Task,
        user,
        agent,
        max_turns: int = 30,
    ):
        self.domain_name = domain_name
        self.initial_db = deep_copy_db(db)
        self.tools = tools
        self.policy = policy
        self.task = task
        self.user = user
        self.agent = agent
        self.max_turns = task.max_turns if task.max_turns > 0 else max_turns

    def run_episode(self) -> EpisodeResult:
        db = deep_copy_db(self.initial_db)

        trajectory: list[TrajectoryStep] = []
        # Agent sees: policy, tool schemas, conversation + tool results
        agent_history: list[dict[str, Any]] = []
        # User sees: only natural language
        user_history: list[dict[str, Any]] = []
        agent_messages: list[str] = []

        turns = 0
        tool_calls = 0
        invalid_tool_calls = 0
        failure_reason: str | None = None
        start_time = time.monotonic()

        # User always opens the conversation
        opening = self.user.start(self.task.instruction)
        trajectory.append(TrajectoryStep(role="user", content={"content": opening}))
        agent_history.append({"role": "user", "content": opening})
        user_history.append({"role": "user", "content": opening})

        tool_schemas = [t.to_schema() for t in self.tools.values()]

        while turns < self.max_turns:
            turns += 1
            action = self.agent.act(
                history=agent_history,
                tools=tool_schemas,
                policy=self.policy,
            )

            if isinstance(action, ToolCall):
                tool_calls += 1
                trajectory.append(TrajectoryStep(role="agent", content=action.model_dump(), metadata={"type": "tool_call"}))

                # LLM providers set _assistant_turn to the exact message dict
                # that belongs in history before the tool result.
                if action._assistant_turn is not None:
                    agent_history.append(action._assistant_turn)

                tool_def = self.tools.get(action.name)
                if tool_def is None:
                    invalid_tool_calls += 1
                    result_str = f"Error: Unknown tool '{action.name}'"
                    result = ToolResult(name=action.name, result=result_str)
                    trajectory.append(TrajectoryStep(role="tool", content=result.model_dump()))
                    if action.tool_call_id:
                        agent_history.append({"role": "tool", "tool_call_id": action.tool_call_id, "content": result_str})
                    else:
                        agent_history.append({"role": "tool", "tool_name": action.name, "content": result_str})
                    continue

                try:
                    raw = tool_def(db, **action.arguments)
                    result = ToolResult(name=action.name, result=raw)
                except TypeError as e:
                    invalid_tool_calls += 1
                    result = ToolResult(name=action.name, result=f"Error: Invalid arguments — {e}")
                except Exception as e:
                    result = ToolResult(name=action.name, result=f"Error: {e}")

                trajectory.append(TrajectoryStep(role="tool", content=result.model_dump()))
                import json
                try:
                    result_str = json.dumps(result.result, ensure_ascii=False) if not isinstance(result.result, str) else result.result
                except Exception:
                    result_str = str(result.result)
                if action.tool_call_id:
                    agent_history.append({"role": "tool", "tool_call_id": action.tool_call_id, "content": result_str})
                else:
                    agent_history.append({"role": "tool", "tool_name": action.name, "content": result_str})

            elif isinstance(action, AgentMessage):
                agent_messages.append(action.content)
                trajectory.append(TrajectoryStep(role="agent", content={"content": action.content}, metadata={"type": "message"}))
                agent_history.append({"role": "assistant", "content": action.content})
                user_history.append({"role": "assistant", "content": action.content})

                user_reply = self.user.respond(action.content, user_history)
                if "###STOP###" in user_reply:
                    trajectory.append(TrajectoryStep(role="user", content={"content": "###STOP###"}, metadata={"stop": True}))
                    break

                trajectory.append(TrajectoryStep(role="user", content={"content": user_reply}))
                agent_history.append({"role": "user", "content": user_reply})
                user_history.append({"role": "user", "content": user_reply})
            else:
                # Unknown action type — skip
                break
        else:
            failure_reason = "max_turns_exceeded"

        latency = time.monotonic() - start_time
        return evaluate_episode(
            task=self.task,
            initial_db=self.initial_db,
            final_db=db,
            agent_messages=agent_messages,
            domain_tools=self.tools,
            trajectory=trajectory,
            provider=getattr(self.agent, "provider_name", None),
            model=getattr(self.agent, "model", None),
            turns=turns,
            tool_calls=tool_calls,
            invalid_tool_calls=invalid_tool_calls,
            latency_seconds=latency,
            failure_reason=failure_reason,
        )
