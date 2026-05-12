"""Core data types for tau-free-bench."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentMessage(BaseModel):
    content: str


class ToolResult(BaseModel):
    name: str
    result: Any


class UserMessage(BaseModel):
    content: str


class TrajectoryStep(BaseModel):
    role: Literal["user", "agent", "tool"]
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: str
    instruction: str
    expected_actions: list[ToolCall] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    max_turns: int = 30
    tags: list[str] = Field(default_factory=list)


class EpisodeResult(BaseModel):
    task_id: str
    reward: int
    action_reward: int
    output_reward: int
    trajectory: list[TrajectoryStep]
    final_db: dict[str, Any]
    expected_db: dict[str, Any]
    db_diff: dict[str, Any]
    agent_messages: list[str]
    failure_reason: str | None = None
    provider: str | None = None
    model: str | None = None
    turns: int = 0
    tool_calls: int = 0
    invalid_tool_calls: int = 0
    latency_seconds: float | None = None
