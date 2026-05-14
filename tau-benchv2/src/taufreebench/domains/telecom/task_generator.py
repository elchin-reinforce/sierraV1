"""Compositional telecom task generator.

For each task we pick a (line, device, customer) triple, choose 1-4 mutually
compatible subtasks from `scenarios.SUBTASKS`, apply their initializers to a
fresh copy of the DB, then verify the task is solvable by replaying the
solution actions through the real agent/user tool implementations and
checking that all assertions flip from FAIL -> PASS.
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

from taufreebench.core.types import DualToolCall, TelecomTask
from .agent_tools import AGENT_TOOLS
from .user_tools import USER_TOOLS
from .assertions import run_assertions
from .scenarios import SUBTASKS


DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "telecom"

PERSONAS = ["none", "easy", "hard"]

# Distribution of subtask counts for a 60-task run.
SUBTASK_COUNT_TARGETS = {1: 24, 2: 20, 3: 12, 4: 4}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _load_dbs() -> tuple[dict[str, Any], dict[str, Any]]:
    agent_db = json.loads((DATA_DIR / "agent_db.json").read_text())
    user_db = json.loads((DATA_DIR / "user_device_db.json").read_text())
    return agent_db, user_db


def _eligible_lines(agent_db: dict[str, Any], user_db: dict[str, Any]) -> list[str]:
    """Lines that are active, have a matching device, and a customer with a
    payment method."""
    out = []
    devices_by_line = {d.get("line_id"): did for did, d in user_db.get("devices", {}).items()}
    for line_id, line in agent_db.get("lines", {}).items():
        if line.get("status") != "active":
            continue
        if line.get("contract_expired"):
            continue
        cust_id = line.get("customer_id")
        cust = agent_db.get("customers", {}).get(cust_id, {})
        if not cust.get("payment_methods"):
            continue
        if line_id not in devices_by_line:
            continue
        out.append(line_id)
    return out


# ---------------------------------------------------------------------------
# Placeholder resolution
# ---------------------------------------------------------------------------

def _first_pm_id(agent_db: dict[str, Any], customer_id: str) -> str | None:
    cust = agent_db.get("customers", {}).get(customer_id, {}) or {}
    pms = cust.get("payment_methods", []) or []
    return pms[0]["id"] if pms else None


def _overdue_bill_id(agent_db: dict[str, Any], customer_id: str) -> str | None:
    for bid, bill in agent_db.get("bills", {}).items():
        if bill.get("customer_id") == customer_id and bill.get("status") == "overdue":
            return bid
    return None


def _bill_amount(agent_db: dict[str, Any], bill_id: str) -> float:
    bill = agent_db.get("bills", {}).get(bill_id, {}) or {}
    val = bill.get("amount", bill.get("amount_usd", 0.0))
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _resolve_placeholders(
    actions: list[DualToolCall],
    assertions: list[dict[str, Any]],
    agent_db: dict[str, Any],
    customer_id: str,
) -> tuple[list[DualToolCall], list[dict[str, Any]]]:
    """Replace placeholder strings like __OVERDUE_BILL__ with real values from
    the *initialized* agent_db."""
    pm = _first_pm_id(agent_db, customer_id)
    overdue_bill = _overdue_bill_id(agent_db, customer_id)
    overdue_amount = _bill_amount(agent_db, overdue_bill) if overdue_bill else 0.0
    if overdue_amount <= 0:
        # make_payment requires amount > 0; pick a sensible positive number.
        overdue_amount = 100.0

    def resolve_val(v: Any) -> Any:
        if v == "__FIRST_PM__":
            return pm
        if v == "__OVERDUE_BILL__":
            return overdue_bill
        if v == "__OVERDUE_AMOUNT__":
            return overdue_amount
        return v

    new_actions: list[DualToolCall] = []
    for a in actions:
        new_args = {k: resolve_val(v) for k, v in a.arguments.items()}
        new_actions.append(DualToolCall(actor=a.actor, name=a.name, arguments=new_args))

    new_assertions: list[dict[str, Any]] = []
    for spec in assertions:
        new_args = {k: resolve_val(v) for k, v in (spec.get("arguments") or {}).items()}
        new_assertions.append({"name": spec["name"], "arguments": new_args})

    return new_actions, new_assertions


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def _replay_action(
    action: DualToolCall,
    agent_db: dict[str, Any],
    user_db: dict[str, Any],
) -> tuple[bool, Any]:
    if action.actor == "agent":
        fn = AGENT_TOOLS.get(action.name)
        if fn is None:
            return False, f"Unknown agent tool: {action.name}"
        try:
            result = fn(agent_db, user_db, **action.arguments)
        except Exception as e:
            return False, f"Exception: {e}"
    else:
        fn = USER_TOOLS.get(action.name)
        if fn is None:
            return False, f"Unknown user tool: {action.name}"
        try:
            result = fn(user_db, agent_db, **action.arguments)
        except Exception as e:
            return False, f"Exception: {e}"
    if isinstance(result, str) and result.startswith("Error"):
        return False, result
    return True, result


# ---------------------------------------------------------------------------
# Subtask selection
# ---------------------------------------------------------------------------

def _pick_subtasks(
    rng: random.Random,
    issue_type: str,
    n: int,
    max_attempts: int = 50,
) -> list[dict[str, Any]] | None:
    pool = [st for st in SUBTASKS if st["issue_type"] == issue_type]
    if n > len(pool):
        return None
    for _ in range(max_attempts):
        chosen = rng.sample(pool, n)
        groups = [st.get("mutually_exclusive_group") for st in chosen if st.get("mutually_exclusive_group")]
        if len(groups) != len(set(groups)):
            continue
        return chosen
    return None


# ---------------------------------------------------------------------------
# Instruction building
# ---------------------------------------------------------------------------

def _build_instruction(
    chosen: list[dict[str, Any]],
    customer: dict[str, Any],
    line_id: str,
    persona: str,
) -> str:
    name = customer.get("name", "the customer")
    first_name = name.split()[0] if name else "the customer"
    phones = customer.get("phone_numbers") or []
    phone = phones[0] if phones else None
    email = customer.get("email")

    user_complaints = [st["description_user"] for st in chosen]
    if len(user_complaints) == 1:
        complaint_text = user_complaints[0]
    else:
        complaint_text = " ".join(user_complaints)

    auth_bits = []
    if phone:
        auth_bits.append(f"phone number {phone}")
    if email:
        auth_bits.append(f"email {email}")
    auth_str = " and ".join(auth_bits) if auth_bits else "your account details"

    base = (
        f"You are {first_name}, a customer calling phone support. "
        f"{complaint_text} "
        f"When asked to authenticate, provide your {auth_str}. "
        f"Cooperate with the support agent — follow their on-device instructions, run the diagnostic checks they request, "
        f"and confirm any changes they need to make on the backend."
    )

    if persona == "easy":
        base += (
            " You are calm, technical, and patient: when the agent asks you to do something on your phone, "
            "do it promptly and report exactly what you see."
        )
    elif persona == "hard":
        base += (
            " You are frustrated and not very technical. Sometimes you complain about the wait or insist the agent "
            "should fix it from their side, but eventually you do what's asked. Don't reveal the diagnosis up front — "
            "let the agent figure it out."
        )
    else:
        # "none" — default neutral persona.
        base += " Respond to the agent's questions matter-of-factly."

    return base


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_task(
    chosen: list[dict[str, Any]],
    line_id: str,
    customer_id: str,
    device_id: str,
    base_agent_db: dict[str, Any],
    base_user_db: dict[str, Any],
) -> tuple[bool, str, list[DualToolCall], list[dict[str, Any]]]:
    """Apply initializers, then replay actions, then check assertions."""
    agent_db = copy.deepcopy(base_agent_db)
    user_db = copy.deepcopy(base_user_db)

    # 1. Initializers (in order).
    for st in chosen:
        try:
            st["initializer"](agent_db, user_db, line_id)
        except Exception as e:
            return False, f"initializer({st['id']}) raised: {e}", [], []

    # 2. Build solution actions (agent actions first, then user actions, in
    #    the order their subtasks appear). This keeps backend prerequisites
    #    (e.g. resume line, reset provisioning) before device-side toggles.
    raw_actions: list[DualToolCall] = []
    raw_assertions: list[dict[str, Any]] = []
    for st in chosen:
        raw_actions.extend(st["solution_actions"](line_id, customer_id, device_id))
        raw_assertions.extend(st["assertions"](line_id, customer_id, device_id))

    actions, assertions = _resolve_placeholders(raw_actions, raw_assertions, agent_db, customer_id)
    # Stable reorder: all agent actions (preserving order) first, then user
    # actions (preserving order). This handles cross-subtask dependencies.
    agent_actions = [a for a in actions if a.actor == "agent"]
    user_actions = [a for a in actions if a.actor == "user"]
    ordered_actions = agent_actions + user_actions

    # 3. Pre-check: assertions should currently fail.
    pre_results = run_assertions(assertions, agent_db, user_db)
    if all(r.get("passed") for r in pre_results):
        return False, "all assertions pass before solution is applied", [], []

    # 4. Replay.
    for action in ordered_actions:
        ok, info = _replay_action(action, agent_db, user_db)
        if not ok:
            return False, f"replay failed for {action.actor}.{action.name}: {info}", [], []

    # 5. Post-check.
    post_results = run_assertions(assertions, agent_db, user_db)
    failing = [r for r in post_results if not r.get("passed")]
    if failing:
        details = "; ".join(f"{r['name']}({r.get('detail')})" for r in failing)
        return False, f"assertions still failing after solution: {details}", [], []

    return True, "ok", ordered_actions, assertions


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def _count_plan(total: int) -> list[int]:
    """Build a list of `total` subtask-count values respecting
    SUBTASK_COUNT_TARGETS, scaling if total != 60."""
    if total == 60:
        plan = []
        for k, n in SUBTASK_COUNT_TARGETS.items():
            plan.extend([k] * n)
        return plan
    # Otherwise scale proportionally.
    plan = []
    scale = total / 60.0
    for k, n in SUBTASK_COUNT_TARGETS.items():
        plan.extend([k] * max(1, int(round(n * scale))))
    while len(plan) < total:
        plan.append(1)
    return plan[:total]


def _issue_type_plan(total: int) -> list[str]:
    per = total // 3
    rem = total - 3 * per
    plan = (["service_issue"] * per
            + ["mobile_data_issue"] * per
            + ["mms_issue"] * per)
    extras = ["service_issue", "mobile_data_issue", "mms_issue"]
    for i in range(rem):
        plan.append(extras[i % 3])
    return plan


def _max_compatible_n(issue_type: str) -> int:
    """Maximum number of mutually-compatible subtasks for an issue type."""
    pool = [st for st in SUBTASKS if st["issue_type"] == issue_type]
    groups_seen: set[str] = set()
    free = 0  # subtasks without a group; each one is independently compatible
    for st in pool:
        g = st.get("mutually_exclusive_group")
        if g:
            groups_seen.add(g)
        else:
            free += 1
    return free + len(groups_seen)


def generate_tasks(count: int = 60, seed: int = 42) -> list[TelecomTask]:
    rng = random.Random(seed)
    base_agent_db, base_user_db = _load_dbs()
    eligible = _eligible_lines(base_agent_db, base_user_db)
    rng.shuffle(eligible)

    devices_by_line = {d.get("line_id"): did for did, d in base_user_db.get("devices", {}).items()}

    count_plan = _count_plan(count)
    issue_plan = _issue_type_plan(count)
    rng.shuffle(count_plan)
    rng.shuffle(issue_plan)

    # Per-issue-type cap on n (since some issue types have small pools).
    max_n_by_issue = {it: _max_compatible_n(it) for it in
                      ("service_issue", "mobile_data_issue", "mms_issue")}

    tasks: list[TelecomTask] = []
    failures: list[str] = []
    line_cursor = 0

    target_idx = 0
    max_total_attempts = count * 80
    attempts_used = 0

    while len(tasks) < count and attempts_used < max_total_attempts:
        attempts_used += 1
        n = count_plan[target_idx % len(count_plan)]
        issue_type = issue_plan[target_idx % len(issue_plan)]
        # Respect per-issue-type maximum.
        effective_n = min(n, max_n_by_issue.get(issue_type, 1))

        # Try several lines for this (n, issue_type) before giving up.
        chosen = None
        result: tuple[bool, str, list[DualToolCall], list[dict[str, Any]]] | None = None
        for _ in range(max(4, len(eligible))):
            line_id = eligible[line_cursor % len(eligible)]
            line_cursor += 1
            line = base_agent_db.get("lines", {}).get(line_id, {}) or {}
            customer_id = line.get("customer_id")
            device_id = devices_by_line.get(line_id)
            if not (customer_id and device_id):
                continue

            for try_n in (effective_n, max(1, effective_n - 1), 1):
                pick = _pick_subtasks(rng, issue_type, try_n)
                if pick is None:
                    continue
                ok, msg, actions, assertions = _validate_task(
                    pick, line_id, customer_id, device_id, base_agent_db, base_user_db
                )
                if ok:
                    chosen = pick
                    result = (ok, msg, actions, assertions)
                    break
                else:
                    failures.append(
                        f"task#{len(tasks)+1} {issue_type} {[s['id'] for s in pick]}: {msg}"
                    )
            if chosen is not None:
                break

        if chosen is None or result is None:
            target_idx += 1
            continue

        _, _, actions, assertions = result
        persona = PERSONAS[len(tasks) % len(PERSONAS)]
        cust = base_agent_db.get("customers", {}).get(customer_id, {}) or {}
        instruction = _build_instruction(chosen, cust, line_id, persona)

        # Compose initializer descriptors (descriptive strings; the env
        # applies the actual mutations via the saved initial DB).
        initializers = [st["id"] for st in chosen]
        tags = sorted({t for st in chosen for t in st.get("tags", [])})
        required_tools = sorted({t for st in chosen for t in st.get("required_tools", [])})
        who_acts = {st.get("who_acts") for st in chosen}
        if "both" in who_acts or who_acts == {"agent", "user"}:
            acting_role = "both"
        elif who_acts == {"agent"}:
            acting_role = "agent"
        elif who_acts == {"user"}:
            acting_role = "user"
        else:
            acting_role = "mixed"

        task = TelecomTask(
            id=f"telecom_{len(tasks)+1:03d}",
            issue_type=issue_type,
            instruction=instruction,
            persona_id=persona,
            initializers=initializers,
            solution_actions=actions,
            assertions=assertions,
            required_outputs=[],
            max_turns=40,
            max_agent_actions=30,
            tags=tags,
            difficulty={
                "n_subtasks": len(chosen),
                "subtask_ids": [s["id"] for s in chosen],
                "required_tools": required_tools,
                "who_acts": acting_role,
                "persona": persona,
            },
            line_id=line_id,
            customer_id=customer_id,
            device_id=device_id,
        )
        tasks.append(task)
        target_idx += 1

    if failures:
        # Surface the first few failures for debugging; this is non-fatal.
        print(f"[generator] {len(failures)} attempts failed; first 5:")
        for f in failures[:5]:
            print(f"  - {f}")

    return tasks


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_tasks(tasks: list[TelecomTask], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [t.model_dump() for t in tasks]
    path.write_text(json.dumps(payload, indent=2))


def main():
    tasks = generate_tasks(count=60)
    out = DATA_DIR / "tasks.json"
    save_tasks(tasks, out)
    print(f"Wrote {len(tasks)} tasks to {out}")

    # Summary breakdown
    from collections import Counter
    by_issue = Counter(t.issue_type for t in tasks)
    by_n = Counter(t.difficulty.get("n_subtasks") for t in tasks)
    by_persona = Counter(t.persona_id for t in tasks)
    by_who = Counter(t.difficulty.get("who_acts") for t in tasks)
    print(f"  issue_type: {dict(by_issue)}")
    print(f"  n_subtasks: {dict(sorted(by_n.items()))}")
    print(f"  persona:    {dict(by_persona)}")
    print(f"  who_acts:   {dict(by_who)}")


if __name__ == "__main__":
    main()
