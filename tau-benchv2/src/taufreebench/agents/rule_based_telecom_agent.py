"""Rule-based telecom agent — deterministic dual-control baseline.

This is a SANITY-CHECK baseline, not a full solver. It walks through a small
state machine, asks the user to perform a few device-side checks, runs a few
backend lookups, and attempts to apply an obvious fix when it can be inferred.
Most tasks are expected to fail; that's fine — the purpose is to verify the
dual-control plumbing works end to end without an LLM in the loop.
"""
from __future__ import annotations
import json
import re
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall
from .dual_base import BaseDualAgent


_ISSUE_SERVICE = "service"
_ISSUE_DATA = "data"
_ISSUE_MMS = "mms"


class RuleBasedTelecomAgent(BaseDualAgent):
    """Hand-coded state machine. No LLM. Useful as a smoke test."""

    provider_name = "rule"
    model = "rule_based_telecom"

    def __init__(self):
        # Auth / customer state
        self._customer_id: str | None = None
        self._line_id: str | None = None
        self._device_id: str | None = None
        self._phone_number: str | None = None
        # Conversation state
        self._issue: str | None = None
        self._phase: str = "AUTH_ASK"
        self._procedure: list[Any] = []   # mix of DualMessage and DualToolCall
        self._proc_idx: int = 0
        self._asked_confirm: bool = False
        self._turn: int = 0

    # ------------------------------------------------------------------
    def act(self, history, tools, policy) -> "DualMessage | DualToolCall":
        self._turn += 1
        last_user_msg = self._last_user_message(history)
        last_tool = self._last_tool_result(history)

        # React to the most recent backend tool result, if any.
        if last_tool is not None:
            reaction = self._on_tool_result(last_tool)
            if reaction is not None:
                return reaction

        # ----- AUTH phase ------------------------------------------------
        if self._phase == "AUTH_ASK":
            self._phase = "AUTH_WAIT"
            return DualMessage(
                actor="agent",
                content=(
                    "Hello, this is telecom support. May I have the phone number "
                    "on the account so I can look you up?"
                ),
            )

        if self._phase == "AUTH_WAIT":
            phone = self._extract_phone(last_user_msg)
            email = self._extract_email(last_user_msg)
            if phone:
                self._phone_number = phone
                return DualToolCall(
                    actor="agent",
                    name="find_customer_by_phone",
                    arguments={"phone_number": phone},
                )
            if email:
                return DualToolCall(
                    actor="agent",
                    name="find_customer_by_email",
                    arguments={"email": email},
                )
            return DualMessage(
                actor="agent",
                content="I just need your phone number (e.g. +1 555 555 1234) or email to look up your account.",
            )

        # ----- DIAGNOSE_OPEN ---------------------------------------------
        if self._phase == "DIAGNOSE_OPEN":
            self._issue = self._detect_issue(history)
            self._build_procedure()
            self._phase = "DIAGNOSE_LOOP"
            return DualMessage(
                actor="agent",
                content=(
                    "Thanks, I've got your account. What's happening on the phone — "
                    "are you seeing any signal bars, or 'no service' in the status bar?"
                ),
            )

        # ----- DIAGNOSE_LOOP: walk the prebuilt procedure ---------------
        if self._phase == "DIAGNOSE_LOOP":
            # (Re)detect the issue if we didn't have it yet (user may have only
            # described the issue in turn 2+).
            if self._issue is None or not self._procedure:
                self._issue = self._detect_issue(history)
                self._build_procedure()

            if self._proc_idx < len(self._procedure):
                step = self._procedure[self._proc_idx]
                self._proc_idx += 1
                return step
            # Out of scripted steps → verify.
            self._phase = "VERIFY"
            return DualMessage(
                actor="agent",
                content="Can you check whether the issue is resolved now?",
            )

        # ----- VERIFY ---------------------------------------------------
        if self._phase == "VERIFY":
            if self._user_affirmative(last_user_msg):
                self._phase = "DONE"
                return DualMessage(
                    actor="agent",
                    content=(
                        "Great, glad we got that sorted. Have a good day!"
                    ),
                )
            if self._user_negative(last_user_msg):
                self._phase = "DONE"
                return DualToolCall(
                    actor="agent",
                    name="transfer_to_human_agent",
                    arguments={"summary": f"Automated troubleshooting did not resolve {self._issue or 'the issue'}."},
                )
            return DualMessage(
                actor="agent",
                content="Please confirm — is everything working now? (yes/no)",
            )

        if self._phase == "DONE":
            return DualMessage(
                actor="agent",
                content="Thanks for calling. Have a good day!",
            )

        # Fallback
        return DualMessage(actor="agent", content="Could you tell me more about the issue?")

    # ------------------------------------------------------------------
    # Tool-result handling
    # ------------------------------------------------------------------
    def _on_tool_result(self, result: dict[str, Any]) -> "DualMessage | DualToolCall | None":
        name = result.get("tool_name") or ""
        content = result.get("content", "")
        parsed: Any = content
        try:
            parsed = json.loads(content)
        except Exception:
            pass
        is_error = (
            isinstance(parsed, str) and parsed.startswith("Error:")
        ) or (isinstance(parsed, dict) and "error" in parsed)

        if name in ("find_customer_by_phone", "find_customer_by_email", "find_customer_by_name_zip"):
            if is_error:
                self._phase = "AUTH_WAIT"
                return DualMessage(
                    actor="agent",
                    content="I couldn't find that account. Could you re-share the phone number or email?",
                )
            cust = parsed if isinstance(parsed, dict) else {}
            self._customer_id = cust.get("customer_id")
            # Pull a likely line / device for use later.
            lines = cust.get("lines") or []
            if isinstance(lines, list) and lines:
                first = lines[0]
                if isinstance(first, dict):
                    self._line_id = first.get("line_id") or self._line_id
            self._phase = "DIAGNOSE_OPEN"
            return None  # next call will handle DIAGNOSE_OPEN

        if name == "get_customer_details" and not is_error:
            cust = parsed if isinstance(parsed, dict) else {}
            for line in cust.get("lines") or []:
                if isinstance(line, dict) and line.get("line_id"):
                    self._line_id = line["line_id"]
                    break
            return None

        if name == "get_line_details" and not is_error and isinstance(parsed, dict):
            self._line_id = parsed.get("line_id") or self._line_id
            return None

        # For most other tool calls, just acknowledge and continue the loop.
        return None

    # ------------------------------------------------------------------
    # Procedure builders per issue
    # ------------------------------------------------------------------
    def _build_procedure(self) -> None:
        if self._procedure:
            return
        device_id = self._device_id or "device_unknown"
        line_id = self._line_id or "line_unknown"
        if self._issue == _ISSUE_SERVICE:
            self._procedure = [
                DualMessage(actor="agent", content="Please open Settings and check whether airplane mode is on."),
                DualMessage(actor="agent", content="Could you turn airplane mode off and check the status bar again?"),
                DualToolCall(actor="agent", name="get_line_details", arguments={"line_id": line_id}),
                DualMessage(actor="agent", content="Let me check whether your line is suspended on our side."),
            ]
        elif self._issue == _ISSUE_DATA:
            self._procedure = [
                DualMessage(actor="agent", content="Could you check that mobile data is turned on under Settings > Mobile Data?"),
                DualMessage(actor="agent", content="Please also check whether Data Saver is on, and turn it off if so."),
                DualMessage(actor="agent", content="Do you have a VPN connected? If yes, please disconnect it."),
                DualToolCall(actor="agent", name="get_data_usage", arguments={"line_id": line_id}),
                DualMessage(actor="agent", content="Now please run a quick speed test on your phone."),
            ]
        elif self._issue == _ISSUE_MMS:
            self._procedure = [
                DualMessage(actor="agent", content="Please open Settings > Apps > Messages and check the MMS permission."),
                DualMessage(actor="agent", content="What does the status bar show for your network — 2G, 3G, 4G or 5G?"),
                DualMessage(actor="agent", content="If it's on 2G, could you switch to 4G in network settings?"),
                DualMessage(actor="agent", content="Please clear the Messages app cache and try sending a test MMS."),
            ]
        else:
            self._procedure = [
                DualMessage(actor="agent", content="Could you tell me a bit more about what's happening on your phone?"),
            ]

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------
    def _detect_issue(self, history: list[dict[str, Any]]) -> str:
        text = " ".join(m.get("content", "") for m in history if m.get("role") == "user").lower()
        if any(k in text for k in ["no service", "no signal", "airplane", "suspended", "can't call", "cant call"]):
            return _ISSUE_SERVICE
        if any(k in text for k in ["picture message", "mms", "send picture", "send a picture", "media message"]):
            return _ISSUE_MMS
        if any(k in text for k in ["data", "slow", "internet", "wifi", "speed", "roaming"]):
            return _ISSUE_DATA
        return _ISSUE_SERVICE

    def _last_user_message(self, history: list[dict[str, Any]]) -> str:
        for msg in reversed(history):
            if msg.get("role") == "user":
                return msg.get("content", "") or ""
        return ""

    def _last_tool_result(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not history:
            return None
        last = history[-1]
        if last.get("role") == "tool":
            return last
        return None

    def _extract_phone(self, text: str) -> str | None:
        if not text:
            return None
        m = re.search(r"\+?\d[\d\s\-().]{7,}", text)
        if not m:
            return None
        raw = m.group(0)
        digits = re.sub(r"[^\d+]", "", raw)
        if digits.startswith("+"):
            return digits
        # Heuristic: 11 digits starting with 1 → +1...
        if len(digits) == 11 and digits.startswith("1"):
            return "+" + digits
        if len(digits) == 10:
            return "+1" + digits
        return digits if len(digits) >= 7 else None

    def _extract_email(self, text: str) -> str | None:
        if not text:
            return None
        m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return m.group(0) if m else None

    def _user_affirmative(self, text: str) -> bool:
        t = (text or "").lower()
        return any(k in t for k in ["yes", "yep", "yeah", "working", "resolved", "###stop###", "fixed", "all good", "all set"])

    def _user_negative(self, text: str) -> bool:
        t = (text or "").lower()
        return any(k in t for k in ["no, ", "nope", "still", "doesn't work", "doesnt work", "didn't work", "didnt work", "not work"])
