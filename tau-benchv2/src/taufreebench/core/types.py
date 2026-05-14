"""Core data types for tau-free-bench / tau-benchv2."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, PrivateAttr


# ============================================================================
# Sierra V2 — Dual-control types (τ²-bench-style)
# ============================================================================

DualActorRole = Literal["agent", "user", "agent_tool", "user_tool", "environment"]
DualActionType = Literal["message", "tool_call"]
DualMode = Literal["default", "no_user", "oracle_plan"]


class DualToolCall(BaseModel):
    """A tool call made by either the agent or the user."""
    actor: Literal["agent", "user"]
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = None
    _assistant_turn: dict[str, Any] | None = PrivateAttr(default=None)


class DualMessage(BaseModel):
    actor: Literal["agent", "user"]
    content: str


class DualToolResult(BaseModel):
    actor: Literal["agent", "user"]
    name: str
    result: Any
    error: bool = False


class DualTrajectoryStep(BaseModel):
    role: DualActorRole
    content: Any
    visible_to_agent: bool
    visible_to_user: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelecomTask(BaseModel):
    id: str
    issue_type: Literal["service_issue", "mobile_data_issue", "mms_issue"]
    instruction: str
    persona_id: str | None = None
    initializers: list[str] = Field(default_factory=list)
    solution_actions: list[DualToolCall] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    max_turns: int = 40
    max_agent_actions: int = 30
    tags: list[str] = Field(default_factory=list)
    difficulty: dict[str, Any] = Field(default_factory=dict)
    line_id: str | None = None
    customer_id: str | None = None
    device_id: str | None = None


class DualEpisodeResult(BaseModel):
    task_id: str
    reward: int
    assertion_reward: int
    output_reward: int
    action_match_reward: int | None = None
    trajectory: list[DualTrajectoryStep] = Field(default_factory=list)
    final_agent_db: dict[str, Any] = Field(default_factory=dict)
    final_user_db: dict[str, Any] = Field(default_factory=dict)
    expected_agent_db: dict[str, Any] | None = None
    expected_user_db: dict[str, Any] | None = None
    assertion_results: list[dict[str, Any]] = Field(default_factory=list)
    db_diff: dict[str, Any] = Field(default_factory=dict)
    compact_diff: dict[str, Any] = Field(default_factory=dict)
    agent_messages: list[str] = Field(default_factory=list)
    user_messages: list[str] = Field(default_factory=list)
    failure_reason: str | None = None
    failure_class: str = "success"
    agent_provider: str | None = None
    agent_model: str | None = None
    user_provider: str | None = None
    user_model: str | None = None
    turns: int = 0
    agent_tool_calls: int = 0
    user_tool_calls: int = 0
    invalid_agent_tool_calls: int = 0
    invalid_user_tool_calls: int = 0
    agent_tool_errors: int = 0
    user_tool_errors: int = 0
    latency_seconds: float | None = None
    mode: DualMode = "default"


# ============================================================================
# Sierra V1 — Single-control types (retain for backward compat)
# ============================================================================



class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = None
    # Set by LLM providers so environment.py can inject the correct assistant
    # message into history before the tool result (not serialized to JSON).
    _assistant_turn: dict[str, Any] | None = PrivateAttr(default=None)


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
    failure_class: str | None = None
    provider: str | None = None
    model: str | None = None
    turns: int = 0
    tool_calls: int = 0
    invalid_tool_calls: int = 0
    latency_seconds: float | None = None
    debug_metadata: dict[str, Any] = Field(default_factory=dict)
