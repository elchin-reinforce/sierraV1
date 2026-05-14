"""Dual-control benchmark environment (τ²-bench-style).

Both agent and user can call tools and affect a shared environment.
"""
from __future__ import annotations
import copy
import time
from typing import Any, Callable

from .types import (
    DualMessage,
    DualToolCall,
    DualToolResult,
    DualTrajectoryStep,
    DualEpisodeResult,
    DualMode,
    TelecomTask,
)

# Sentinels the user can emit to terminate the conversation.
STOP_TOKENS = ("###STOP###", "###TRANSFER###", "###OUT-OF-SCOPE###")

# Agent tool names that represent a real transfer-to-human action.
TRANSFER_TOOL_NAMES = {
    "transfer_to_human_agent",
    "transfer_to_human_agents",
    "transfer",
}

# Phrases that indicate the agent has actually told the user they are being
# transferred. The check is case-insensitive and substring-based.
TRANSFER_MESSAGE_PHRASES = (
    "you are being transferred",
    "you're being transferred",
    "transferring you to a human",
    "transferring you to an agent",
    "transferred to a human agent",
    "transferred to an agent",
    "i am transferring you",
    "i'm transferring you",
    "i am connecting you to a human",
    "i'm connecting you to a human",
    "we are transferring you",
    "we're transferring you",
)

# Max reprompts allowed when the user emits ###TRANSFER### before the agent
# has actually performed the transfer protocol. Two attempts per episode.
MAX_TRANSFER_REPROMPTS = 2

REPROMPT_INSTRUCTION = (
    "[SYSTEM CORRECTION TO YOU, THE CUSTOMER]: Your previous response incorrectly "
    "emitted ###TRANSFER###. The support agent has NOT actually transferred you yet. "
    "You may only emit ###TRANSFER### AFTER the agent has called the transfer tool "
    "AND told you that you are being transferred to a human agent. "
    "If the agent merely asked whether you want to be transferred or hinted at "
    "escalation, answer them naturally — for example: 'Yes, please transfer me.' "
    "Continue the conversation as the customer. Do not emit any terminal token "
    "unless the scenario goal is truly complete."
)


def _has_agent_completed_transfer(trajectory) -> bool:
    """Return True iff the trajectory shows the agent both:
       1. called a transfer tool, AND
       2. sent a natural-language confirmation that the user is being transferred.

    Used to validate ###TRANSFER### from the user simulator.
    """
    saw_transfer_tool = False
    saw_transfer_message = False
    for step in trajectory:
        role = getattr(step, "role", None)
        content = getattr(step, "content", None)
        if role == "agent_tool" and isinstance(content, dict):
            name = content.get("name") or content.get("tool") or ""
            if name in TRANSFER_TOOL_NAMES:
                saw_transfer_tool = True
        elif role == "agent" and isinstance(content, dict):
            text = (content.get("content") or "").lower()
            if any(phrase in text for phrase in TRANSFER_MESSAGE_PHRASES):
                saw_transfer_message = True
    return saw_transfer_tool and saw_transfer_message


class DualControlEnvironment:
    """Runs a dual-control episode: agent ↔ user, both with tools."""

    def __init__(
        self,
        domain_name: str,
        agent_db: dict[str, Any],
        user_db: dict[str, Any],
        agent_tools: dict[str, Callable],
        user_tools: dict[str, Callable],
        policy: str,
        task: TelecomTask,
        user_simulator,
        agent,
        mode: DualMode = "default",
        max_turns: int = 40,
        max_agent_actions: int = 30,
    ):
        self.domain_name = domain_name
        self.agent_db = copy.deepcopy(agent_db)
        self.user_db = copy.deepcopy(user_db)
        self.agent_tools = agent_tools
        self.user_tools = user_tools
        self.policy = policy
        self.task = task
        self.user_simulator = user_simulator
        self.agent = agent
        self.mode = mode
        self.max_turns = task.max_turns if task.max_turns else max_turns
        self.max_agent_actions = task.max_agent_actions if task.max_agent_actions else max_agent_actions

    def run_episode(self) -> DualEpisodeResult:
        trajectory: list[DualTrajectoryStep] = []
        agent_history: list[dict[str, Any]] = []
        user_history: list[dict[str, Any]] = []
        agent_messages: list[str] = []
        user_messages: list[str] = []

        turns = 0
        agent_actions = 0
        agent_tool_calls = 0
        user_tool_calls = 0
        invalid_agent_tool_calls = 0
        invalid_user_tool_calls = 0
        agent_tool_errors = 0
        user_tool_errors = 0
        failure_reason: str | None = None
        start_time = time.monotonic()

        # ----- Mode setup ---------------------------------------------------
        if self.mode == "no_user":
            # No user simulator. Agent receives a ticket and controls both
            # sides' tools directly.
            ticket = (
                f"[Internal ticket — no user available]\n"
                f"Issue: {self.task.issue_type}\n"
                f"Description: {self.task.instruction}\n"
                f"You have access to BOTH backend and device tools. Resolve the issue."
            )
            opening = ticket
            agent_history.append({"role": "user", "content": opening})
            trajectory.append(DualTrajectoryStep(
                role="environment", content={"content": opening},
                visible_to_agent=True, visible_to_user=False,
                metadata={"event": "ticket_open"},
            ))
        else:
            # Paper-aligned: the user knows its own device_id, line_id, and
            # customer_id (these are personal context, like knowing your own
            # phone). Inject them into the hidden instruction so user-side
            # tools (which require those IDs) can be called correctly.
            id_context = (
                f"YOUR ACCOUNT CONTEXT (pass these exact IDs to user tools):\n"
                f"- device_id: {self.task.device_id}\n"
                f"- line_id: {self.task.line_id}\n"
                f"- customer_id: {self.task.customer_id}\n\n"
            )
            full_instruction = id_context + self.task.instruction
            opening = self.user_simulator.start(full_instruction)
            user_messages.append(opening)
            agent_history.append({"role": "user", "content": opening})
            user_history.append({"role": "assistant", "content": opening})
            trajectory.append(DualTrajectoryStep(
                role="user", content={"content": opening},
                visible_to_agent=True, visible_to_user=True,
            ))

        # Schemas the agent and user expose to their respective LLMs.
        agent_tool_schemas = [self._tool_schema(t) for t in self.agent_tools.values()]
        user_tool_schemas = [self._tool_schema(t) for t in self.user_tools.values()]
        if self.mode == "no_user":
            agent_tool_schemas = agent_tool_schemas + user_tool_schemas

        # Optional oracle plan: prepend ground-truth high-level plan to history.
        if self.mode == "oracle_plan":
            plan_text = self._build_plan_text()
            agent_history.insert(0, {
                "role": "system",
                "content": f"[Oracle plan — ground-truth high-level plan]\n{plan_text}",
            })
            trajectory.append(DualTrajectoryStep(
                role="environment", content={"content": plan_text},
                visible_to_agent=True, visible_to_user=False,
                metadata={"event": "oracle_plan"},
            ))

        # ----- Main loop ----------------------------------------------------
        while turns < self.max_turns:
            turns += 1

            # Agent's turn
            agent_action = self._agent_act(agent_history, agent_tool_schemas)

            if isinstance(agent_action, DualToolCall):
                agent_actions += 1
                agent_tool_calls += 1
                trajectory.append(DualTrajectoryStep(
                    role="agent_tool", content=agent_action.model_dump(),
                    visible_to_agent=True, visible_to_user=False,
                ))
                if agent_action._assistant_turn is not None:
                    agent_history.append(agent_action._assistant_turn)

                # Look up tool in agent's tool set (which in no-user mode
                # also contains user tools).
                tool_fn = self.agent_tools.get(agent_action.name) or (
                    self.user_tools.get(agent_action.name) if self.mode == "no_user" else None
                )
                if tool_fn is None:
                    invalid_agent_tool_calls += 1
                    result_str = f"Error: Unknown tool '{agent_action.name}'"
                    self._append_tool_result_to_history(agent_history, agent_action, result_str)
                    trajectory.append(DualTrajectoryStep(
                        role="agent_tool", content={"error": result_str},
                        visible_to_agent=True, visible_to_user=False,
                    ))
                    continue

                result = self._invoke_tool(tool_fn, agent_action.arguments, actor="agent")
                if isinstance(result, str) and result.startswith("Error:"):
                    agent_tool_errors += 1
                result_str = self._stringify(result)
                self._append_tool_result_to_history(agent_history, agent_action, result_str)
                trajectory.append(DualTrajectoryStep(
                    role="agent_tool",
                    content={"name": agent_action.name, "result": result, "args": agent_action.arguments},
                    visible_to_agent=True, visible_to_user=False,
                ))

                if agent_actions >= self.max_agent_actions:
                    failure_reason = "max_agent_actions_exceeded"
                    break
                continue

            if isinstance(agent_action, DualMessage):
                agent_actions += 1
                agent_messages.append(agent_action.content)
                agent_history.append({"role": "assistant", "content": agent_action.content})
                if self.mode != "no_user":
                    user_history.append({"role": "user", "content": agent_action.content})
                trajectory.append(DualTrajectoryStep(
                    role="agent", content={"content": agent_action.content},
                    visible_to_agent=True, visible_to_user=(self.mode != "no_user"),
                ))

                if self.mode == "no_user":
                    # No user reply needed. Continue or stop if agent emits sentinel.
                    if any(t in agent_action.content for t in STOP_TOKENS):
                        break
                    continue

                # User's turn -------------------------------------------------
                # The user may call tools first, then send a message. Loop until
                # the user actually emits a message (or until we hit a safety cap).
                user_tool_budget = 6  # max sequential tool calls in one user turn
                reprompt_count = getattr(self, "_reprompt_count", 0)
                got_user_message = False
                _stopped = False
                while user_tool_budget > 0:
                    user_action = self._user_act(user_history, user_tool_schemas)

                    if isinstance(user_action, DualToolCall):
                        user_tool_budget -= 1
                        user_tool_calls += 1
                        trajectory.append(DualTrajectoryStep(
                            role="user_tool", content=user_action.model_dump(),
                            visible_to_agent=False, visible_to_user=True,
                        ))
                        if user_action._assistant_turn is not None:
                            user_history.append(user_action._assistant_turn)

                        tool_fn = self.user_tools.get(user_action.name)
                        if tool_fn is None:
                            invalid_user_tool_calls += 1
                            result_str = f"Error: Unknown tool '{user_action.name}'"
                            self._append_tool_result_to_history(user_history, user_action, result_str)
                            continue

                        result = self._invoke_tool(tool_fn, user_action.arguments, actor="user")
                        if isinstance(result, str) and result.startswith("Error:"):
                            user_tool_errors += 1
                        result_str = self._stringify(result)
                        self._append_tool_result_to_history(user_history, user_action, result_str)
                        trajectory.append(DualTrajectoryStep(
                            role="user_tool",
                            content={"name": user_action.name, "result": result, "args": user_action.arguments},
                            visible_to_agent=False, visible_to_user=True,
                        ))
                        continue

                    if isinstance(user_action, DualMessage):
                        content = user_action.content
                        # Deterministic guardrail: reject ###TRANSFER### unless
                        # the agent has actually performed the transfer protocol.
                        is_transfer = "###TRANSFER###" in content
                        if is_transfer and not _has_agent_completed_transfer(trajectory):
                            # Premature transfer — log and reprompt (or fail if past limit).
                            trajectory.append(DualTrajectoryStep(
                                role="environment",
                                content={
                                    "event": "invalid_premature_transfer",
                                    "raw_user_output": content,
                                    "agent_last_message": agent_messages[-1] if agent_messages else None,
                                    "transfer_tool_seen": False,
                                    "transfer_message_seen": False,
                                    "reprompt_attempt": reprompt_count + 1,
                                },
                                visible_to_agent=False,
                                visible_to_user=False,
                                metadata={"event_type": "premature_transfer"},
                            ))
                            if reprompt_count < MAX_TRANSFER_REPROMPTS:
                                reprompt_count += 1
                                self._reprompt_count = reprompt_count
                                # Inject a corrective "agent-like" message so the
                                # user simulator sees the correction on its next turn.
                                user_history.append({
                                    "role": "user",
                                    "content": REPROMPT_INSTRUCTION,
                                })
                                # Loop again to give the user another chance.
                                continue
                            else:
                                # Exceeded reprompts — accept termination but classify
                                # explicitly as a simulator-side premature failure.
                                got_user_message = True
                                user_messages.append(content)
                                user_history.append({"role": "assistant", "content": content})
                                agent_history.append({"role": "user", "content": content})
                                trajectory.append(DualTrajectoryStep(
                                    role="user", content={"content": content},
                                    visible_to_agent=True, visible_to_user=True,
                                    metadata={"outcome": "premature_transfer_after_reprompt"},
                                ))
                                failure_reason = "premature_transfer_after_reprompt"
                                _stopped = True
                                break

                        # Normal acceptance path
                        got_user_message = True
                        user_messages.append(content)
                        user_history.append({"role": "assistant", "content": content})
                        agent_history.append({"role": "user", "content": content})
                        trajectory.append(DualTrajectoryStep(
                            role="user", content={"content": content},
                            visible_to_agent=True, visible_to_user=True,
                        ))
                        if any(token in content for token in STOP_TOKENS):
                            failure_reason = self._sentinel_reason(content)
                            _stopped = True
                        break

                    # Unknown action — break user turn
                    break

                if _stopped:
                    break
                if not got_user_message:
                    # User burned through their tool budget without sending a message.
                    # Inject a placeholder user message so the agent's next call has
                    # a user-ending history.
                    placeholder = "(thinking...)"
                    agent_history.append({"role": "user", "content": placeholder})
                continue

            # Unknown agent action type
            failure_reason = "unknown_action_type"
            break

        else:
            failure_reason = "max_turns_exceeded"

        latency = time.monotonic() - start_time

        # ----- Evaluation ---------------------------------------------------
        from .dual_evaluator import evaluate_dual_episode
        result = evaluate_dual_episode(
            task=self.task,
            agent_db=self.agent_db,
            user_db=self.user_db,
            agent_messages=agent_messages,
            user_messages=user_messages,
            agent_tools=self.agent_tools,
            user_tools=self.user_tools,
            trajectory=trajectory,
            mode=self.mode,
            failure_reason=failure_reason,
            turns=turns,
            agent_tool_calls=agent_tool_calls,
            user_tool_calls=user_tool_calls,
            invalid_agent_tool_calls=invalid_agent_tool_calls,
            invalid_user_tool_calls=invalid_user_tool_calls,
            agent_tool_errors=agent_tool_errors,
            user_tool_errors=user_tool_errors,
            latency_seconds=latency,
            agent_provider=getattr(self.agent, "provider_name", None),
            agent_model=getattr(self.agent, "model", None),
            user_provider=getattr(self.user_simulator, "provider_name", None) if self.mode != "no_user" else None,
            user_model=getattr(self.user_simulator, "model", None) if self.mode != "no_user" else None,
        )
        return result

    # ----- Helpers ----------------------------------------------------------
    def _agent_act(self, history, tool_schemas):
        return self.agent.act(history=history, tools=tool_schemas, policy=self.policy)

    def _user_act(self, history, tool_schemas):
        return self.user_simulator.act(
            history=history,
            tools=tool_schemas,
            persona_id=self.task.persona_id,
        )

    def _invoke_tool(self, tool_fn, arguments, actor):
        try:
            if actor == "agent":
                return tool_fn(self.agent_db, self.user_db, **arguments)
            return tool_fn(self.user_db, self.agent_db, **arguments)
        except TypeError as e:
            return f"Error: Invalid arguments — {e}"
        except Exception as e:
            return f"Error: {e}"

    def _stringify(self, result) -> str:
        import json
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)

    def _append_tool_result_to_history(self, history, action, result_str):
        if action.tool_call_id:
            history.append({
                "role": "tool",
                "tool_call_id": action.tool_call_id,
                "content": result_str,
            })
        else:
            history.append({
                "role": "tool",
                "tool_name": action.name,
                "content": result_str,
            })

    def _tool_schema(self, tool_fn) -> dict[str, Any]:
        """Tool functions expose `_schema` attribute set by the @tool decorator."""
        schema = getattr(tool_fn, "_schema", None)
        if schema:
            return schema
        return {"name": getattr(tool_fn, "__name__", "unknown"),
                "description": getattr(tool_fn, "__doc__", "") or "",
                "parameters": {"type": "object", "properties": {}}}

    def _sentinel_reason(self, message: str) -> str | None:
        if "###STOP###" in message:
            return None  # successful stop is not a failure
        if "###TRANSFER###" in message:
            return "user_transfer"
        if "###OUT-OF-SCOPE###" in message:
            return "out_of_scope"
        return None

    def _build_plan_text(self) -> str:
        lines = [f"Issue type: {self.task.issue_type}", "Required actions:"]
        for i, action in enumerate(self.task.solution_actions, 1):
            lines.append(f"  {i}. {action.actor}.{action.name}({action.arguments})")
        if self.task.assertions:
            lines.append("Success criteria:")
            for a in self.task.assertions:
                lines.append(f"  - {a.get('name', 'assertion')}({a.get('arguments', {})})")
        return "\n".join(lines)
