"""Deterministic dual-control user simulator driven by a task's solution actions."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall
from .dual_user_base import BaseDualUser


# ---------------------------------------------------------------------------
# Opening utterances per issue type
# ---------------------------------------------------------------------------
_OPENINGS = {
    "service_issue": "Hi, my phone has no service. Can you help?",
    "mobile_data_issue": "Hi, my mobile data is really slow today.",
    "mms_issue": "Hi, I can't send picture messages.",
}

# Friendly acknowledgements interleaved with tool calls.
_ACKS = [
    "OK, done.",
    "Alright, I did that.",
    "Done — anything else?",
    "Got it, what's next?",
]


def _find_tasks_file() -> Path:
    # Try a few locations: package-relative, repo-rooted, env override.
    candidates: list[Path] = []
    env = os.environ.get("TAUFREE_TELECOM_TASKS")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    # src/taufreebench/users/ -> repo/data/telecom/tasks.json
    candidates.append(here.parents[3] / "data" / "telecom" / "tasks.json")
    candidates.append(here.parents[4] / "data" / "telecom" / "tasks.json")
    candidates.append(Path.cwd() / "data" / "telecom" / "tasks.json")
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not locate data/telecom/tasks.json — set TAUFREE_TELECOM_TASKS env var."
    )


def _load_task(task_id: str) -> dict[str, Any]:
    path = _find_tasks_file()
    with open(path) as f:
        tasks = json.load(f)
    for t in tasks:
        if t.get("id") == task_id:
            return t
    raise KeyError(f"Task not found: {task_id}")


class ScriptedDualUser(BaseDualUser):
    """User that replays the user-side solution_actions from a task.

    Behaviour:
      - `start()` returns a fixed opening tied to the issue type.
      - `act()` alternates between popping the next queued user-side tool call
        and sending a short natural-language acknowledgement.
      - When the queue is exhausted, emits a final "###STOP###" message.
      - If the agent message mentions transferring to a human, emits "###TRANSFER###".
    """

    provider_name = "scripted"
    model = "scripted_dual_user"

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._task = _load_task(task_id)
        # Filter for user-actor solution actions only.
        self._queue: list[dict[str, Any]] = [
            sa for sa in self._task.get("solution_actions", [])
            if sa.get("actor") == "user"
        ]
        self._issue_type = self._task.get("issue_type", "")
        self._ack_idx = 0
        self._send_ack_next = False
        self._started = False
        self._stopped = False

    # ------------------------------------------------------------------
    def start(self, instruction: str) -> str:
        self._started = True
        return _OPENINGS.get(self._issue_type, "Hi, I'm having an issue with my phone.")

    def act(self, history, tools, persona_id) -> "DualMessage | DualToolCall":
        # Look at the latest agent message.
        last_agent = ""
        for msg in reversed(history):
            if msg.get("role") == "user":  # from the user-sim's POV, agent msgs arrive as role=user
                last_agent = msg.get("content", "") or ""
                break

        lower = last_agent.lower()

        # Transfer / out-of-scope detection
        if "transfer" in lower or "human agent" in lower or "human representative" in lower:
            return DualMessage(actor="user", content="OK, ###TRANSFER###")

        # If queue is exhausted, finish.
        if not self._queue:
            if not self._stopped:
                self._stopped = True
                return DualMessage(actor="user", content="Looks good, all working now. ###STOP###")
            return DualMessage(actor="user", content="###STOP###")

        # If the agent is clearly asking for confirmation but no device action is implied yet,
        # answer "yes" before performing the next tool call.
        if self._send_ack_next:
            self._send_ack_next = False
            ack = _ACKS[self._ack_idx % len(_ACKS)]
            self._ack_idx += 1
            return DualMessage(actor="user", content=ack)

        # Pop the next queued user action and emit it as a DualToolCall.
        nxt = self._queue.pop(0)
        name = nxt.get("name", "")
        args = dict(nxt.get("arguments", {}) or {})
        # Schedule a short acknowledgement on the next turn so we don't
        # spam the agent with consecutive tool calls without explanation.
        self._send_ack_next = True
        return DualToolCall(actor="user", name=name, arguments=args)
