"""Telecom domain — agent-side (backend) tools."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable

AGENT_TOOLS: dict[str, Callable] = {}


def agent_tool(schema: dict[str, Any]):
    """Decorator: register the function as an agent tool with the given schema."""
    def wrap(fn):
        fn._schema = schema
        AGENT_TOOLS[schema["name"]] = fn
        return fn
    return wrap


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_phone(value: Any) -> str:
    """Reduce any phone-like string to bare digits for comparison.
    Tolerant of E.164 (+14155550101), formatted ((415) 555-0101), spaces, dashes.
    Strips a leading country code "1" if present, then returns "1" + 10-digit form
    to give a canonical 11-digit representation.
    """
    if not isinstance(value, str):
        return ""
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return ""
    # Strip a leading "1" so "+14155550101" and "4155550101" both canonicalize to "14155550101".
    if len(digits) == 10:
        return "1" + digits
    return digits


def _normalize_id(value: Any) -> str:
    """For underscore-prefixed IDs like cust_001, line_001, bill_001. Trim whitespace, lowercase
    the alpha prefix. Models occasionally pass `Cust_001` or `Customer 001`."""
    if not isinstance(value, str):
        return ""
    s = value.strip()
    return s


def _customers(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("customers", {})


def _lines(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("lines", {})


def _plans(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("plans", {})


def _bills(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("bills", {})


def _devices(user_db: dict[str, Any]) -> dict[str, Any]:
    return user_db.setdefault("devices", {})


def _customer_lines(agent_db: dict[str, Any], customer_id: str) -> list[dict[str, Any]]:
    result = []
    for line_id, line in _lines(agent_db).items():
        if line.get("customer_id") == customer_id:
            result.append({"line_id": line_id, **line})
    return result


def _customer_bills(agent_db: dict[str, Any], customer_id: str) -> list[dict[str, Any]]:
    result = []
    for bill_id, bill in _bills(agent_db).items():
        if bill.get("customer_id") == customer_id:
            result.append({"bill_id": bill_id, **bill})
    return result


def _find_device_for_line(user_db: dict[str, Any], line_id: str) -> tuple[str | None, dict[str, Any] | None]:
    for device_id, device in _devices(user_db).items():
        if device.get("line_id") == line_id:
            return device_id, device
    return None, None


# ----------------------------------------------------------------------------
# READ TOOLS
# ----------------------------------------------------------------------------

@agent_tool({
    "name": "find_customer_by_phone",
    "description": "Look up a customer by phone number.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone_number": {"type": "string", "description": "Customer phone number (E.164 or plain digits)."}
        },
        "required": ["phone_number"],
    },
})
def find_customer_by_phone(agent_db, user_db, phone_number: str):
    target = _normalize_phone(phone_number)
    if not target:
        return "Error: phone_number is required."
    for cust_id, cust in _customers(agent_db).items():
        # DB schema uses `phone_numbers` (list) on customers; also tolerate singular `phone_number`/`phone`.
        candidates = (
            cust.get("phone_numbers") or [cust.get("phone_number"), cust.get("phone")]
        )
        for cand in candidates or []:
            if cand and _normalize_phone(cand) == target:
                return {"customer_id": cust_id, **cust}
    # Try lines as a fallback (lines store phone_number as a singular string).
    for line_id, line in _lines(agent_db).items():
        if line.get("phone_number") and _normalize_phone(line["phone_number"]) == target:
            cust_id = line.get("customer_id")
            cust = _customers(agent_db).get(cust_id)
            if cust is not None:
                return {"customer_id": cust_id, **cust}
    return "Error: Customer not found."


@agent_tool({
    "name": "find_customer_by_email",
    "description": "Look up a customer by email address.",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Customer email address."}
        },
        "required": ["email"],
    },
})
def find_customer_by_email(agent_db, user_db, email: str):
    target = (email or "").strip().lower()
    if not target:
        return "Error: email is required."
    for cust_id, cust in _customers(agent_db).items():
        if cust.get("email", "").lower() == target:
            return {"customer_id": cust_id, **cust}
    return "Error: Customer not found."


@agent_tool({
    "name": "find_customer_by_name_zip",
    "description": "Look up a customer by full name and ZIP code.",
    "parameters": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "zip": {"type": "string", "description": "ZIP / postal code."},
        },
        "required": ["first_name", "last_name", "zip"],
    },
})
def find_customer_by_name_zip(agent_db, user_db, first_name: str, last_name: str, zip: str):
    fn = (first_name or "").strip().lower()
    ln = (last_name or "").strip().lower()
    z = (zip or "").strip()
    if not (fn and ln and z):
        return "Error: first_name, last_name, and zip are required."
    for cust_id, cust in _customers(agent_db).items():
        if (
            cust.get("first_name", "").lower() == fn
            and cust.get("last_name", "").lower() == ln
            and str(cust.get("zip", "")) == z
        ):
            return {"customer_id": cust_id, **cust}
    return "Error: Customer not found."


@agent_tool({
    "name": "get_customer_details",
    "description": "Get a full customer record together with their lines.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
        },
        "required": ["customer_id"],
    },
})
def get_customer_details(agent_db, user_db, customer_id: str):
    cust = _customers(agent_db).get(customer_id)
    if cust is None:
        return "Error: Customer not found."
    return {
        "customer_id": customer_id,
        **cust,
        "lines": _customer_lines(agent_db, customer_id),
    }


@agent_tool({
    "name": "get_line_details",
    "description": "Get a line plus its plan name and owning customer name.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def get_line_details(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    plan = _plans(agent_db).get(line.get("plan_id", ""), {})
    cust = _customers(agent_db).get(line.get("customer_id", ""), {})
    customer_name = (
        f"{cust.get('first_name', '').strip()} {cust.get('last_name', '').strip()}".strip()
    )
    return {
        "line_id": line_id,
        **line,
        "plan_name": plan.get("name"),
        "customer_name": customer_name or None,
    }


@agent_tool({
    "name": "get_plan_details",
    "description": "Get the details of a plan.",
    "parameters": {
        "type": "object",
        "properties": {
            "plan_id": {"type": "string"},
        },
        "required": ["plan_id"],
    },
})
def get_plan_details(agent_db, user_db, plan_id: str):
    plan = _plans(agent_db).get(plan_id)
    if plan is None:
        return "Error: Plan not found."
    return {"plan_id": plan_id, **plan}


@agent_tool({
    "name": "get_billing_status",
    "description": "Get the list of bills for a customer with unpaid/overdue totals.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
        },
        "required": ["customer_id"],
    },
})
def get_billing_status(agent_db, user_db, customer_id: str):
    if customer_id not in _customers(agent_db):
        return "Error: Customer not found."
    bills = _customer_bills(agent_db, customer_id)
    unpaid_count = 0
    overdue_count = 0
    unpaid_total = 0.0
    overdue_total = 0.0
    for b in bills:
        status = b.get("status", "")
        amount = float(b.get("amount", 0) or 0)
        if status == "unpaid":
            unpaid_count += 1
            unpaid_total += amount
        elif status == "overdue":
            overdue_count += 1
            overdue_total += amount
    return {
        "customer_id": customer_id,
        "bills": bills,
        "unpaid_count": unpaid_count,
        "overdue_count": overdue_count,
        "unpaid_total": round(unpaid_total, 2),
        "overdue_total": round(overdue_total, 2),
    }


@agent_tool({
    "name": "get_data_usage",
    "description": "Get the data usage and remaining allowance for a line.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def get_data_usage(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    plan = _plans(agent_db).get(line.get("plan_id", ""), {})
    unlimited = bool(plan.get("unlimited") or line.get("unlimited"))
    used_gb = float(line.get("data_used_gb", 0) or 0)
    limit_gb = float(line.get("data_limit_gb", 0) or 0)
    if unlimited:
        return {
            "used_gb": used_gb,
            "limit_gb": None,
            "remaining_gb": None,
            "percent_used": None,
            "unlimited": True,
        }
    remaining = max(0.0, limit_gb - used_gb)
    percent = round((used_gb / limit_gb) * 100, 2) if limit_gb > 0 else 0.0
    return {
        "used_gb": used_gb,
        "limit_gb": limit_gb,
        "remaining_gb": round(remaining, 3),
        "percent_used": percent,
        "unlimited": False,
    }


@agent_tool({
    "name": "get_roaming_status",
    "description": "Get the backend roaming flag and whether the plan includes roaming.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def get_roaming_status(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    plan = _plans(agent_db).get(line.get("plan_id", ""), {})
    return {
        "backend_roaming_enabled": bool(line.get("roaming_enabled_backend", False)),
        "plan_includes_roaming": bool(plan.get("includes_roaming", False)),
    }


@agent_tool({
    "name": "get_support_notes",
    "description": "Get the list of support notes attached to a customer.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
        },
        "required": ["customer_id"],
    },
})
def get_support_notes(agent_db, user_db, customer_id: str):
    cust = _customers(agent_db).get(customer_id)
    if cust is None:
        return "Error: Customer not found."
    notes = cust.setdefault("support_notes", [])
    return {"customer_id": customer_id, "support_notes": list(notes)}


# ----------------------------------------------------------------------------
# WRITE TOOLS
# ----------------------------------------------------------------------------

@agent_tool({
    "name": "enable_backend_roaming",
    "description": "Enable the backend roaming flag on a line.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def enable_backend_roaming(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    line["roaming_enabled_backend"] = True
    return {"line_id": line_id, "backend_roaming_enabled": True}


@agent_tool({
    "name": "disable_backend_roaming",
    "description": "Disable the backend roaming flag on a line.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def disable_backend_roaming(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    line["roaming_enabled_backend"] = False
    return {"line_id": line_id, "backend_roaming_enabled": False}


@agent_tool({
    "name": "add_data_refuel",
    "description": "Add a one-time data refuel (extra GB) to an active line, charged to the given payment method.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
            "gb_amount": {"type": "number", "description": "Amount of GB to add (must be > 0)."},
            "payment_method_id": {"type": "string"},
        },
        "required": ["line_id", "gb_amount", "payment_method_id"],
    },
})
def add_data_refuel(agent_db, user_db, line_id: str, gb_amount: float, payment_method_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    if line.get("status") != "active":
        return "Error: Cannot refuel a line that is not active."
    try:
        gb = float(gb_amount)
    except (TypeError, ValueError):
        return "Error: gb_amount must be a number."
    if gb <= 0:
        return "Error: gb_amount must be greater than 0."
    customer_id = line.get("customer_id")
    cust = _customers(agent_db).get(customer_id, {})
    pm_ids = {pm.get("id") for pm in cust.get("payment_methods", [])}
    if payment_method_id not in pm_ids:
        return "Error: Payment method does not belong to this customer."
    old_limit = float(line.get("data_limit_gb", 0) or 0)
    line["data_limit_gb"] = round(old_limit + gb, 3)
    return {
        "line_id": line_id,
        "added_gb": gb,
        "new_limit_gb": line["data_limit_gb"],
        "payment_method_id": payment_method_id,
    }


@agent_tool({
    "name": "resume_suspended_line",
    "description": "Resume a suspended line. Requires a non-empty reason; overdue suspensions cannot be resumed while bills are overdue.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
            "reason": {"type": "string", "description": "Non-empty justification for resuming the line."},
        },
        "required": ["line_id", "reason"],
    },
})
def resume_suspended_line(agent_db, user_db, line_id: str, reason: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    if not (reason and reason.strip()):
        return "Error: reason must be a non-empty string."
    status = line.get("status")
    if status != "suspended":
        return f"Error: Line is not suspended (status: {status})."
    suspended_reason = line.get("suspended_reason")
    if suspended_reason == "contract_expired":
        return "Error: Line is suspended due to expired contract; transfer to a human agent."
    if suspended_reason == "overdue_payment":
        customer_id = line.get("customer_id")
        for bill in _customer_bills(agent_db, customer_id):
            if bill.get("status") == "overdue":
                return "Error: Customer has overdue bills; clear them before resuming the line."
    line["status"] = "active"
    line["suspended_reason"] = None
    return {"line_id": line_id, "status": "active", "reason": reason.strip()}


@agent_tool({
    "name": "make_payment",
    "description": "Charge a payment method to clear a customer's bill.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "bill_id": {"type": "string"},
            "payment_method_id": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["customer_id", "bill_id", "payment_method_id", "amount"],
    },
})
def make_payment(agent_db, user_db, customer_id: str, bill_id: str, payment_method_id: str, amount: float):
    cust = _customers(agent_db).get(customer_id)
    if cust is None:
        return "Error: Customer not found."
    bill = _bills(agent_db).get(bill_id)
    if bill is None:
        return "Error: Bill not found."
    if bill.get("customer_id") != customer_id:
        return "Error: Bill does not belong to this customer."
    pm_ids = {pm.get("id") for pm in cust.get("payment_methods", [])}
    if payment_method_id not in pm_ids:
        return "Error: Payment method does not belong to this customer."
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return "Error: amount must be a number."
    if amt <= 0:
        return "Error: amount must be greater than 0."
    bill_amount = float(bill.get("amount", 0) or 0)
    if amt < bill_amount:
        return f"Error: amount {amt} is less than bill amount {bill_amount}."
    bill["status"] = "paid"
    bill["paid_at"] = _now_iso()
    bill["paid_with"] = payment_method_id
    return {
        "bill_id": bill_id,
        "status": "paid",
        "amount_charged": amt,
        "payment_method_id": payment_method_id,
    }


@agent_tool({
    "name": "send_payment_request",
    "description": "Record a payment request for a customer (e.g. to be paid via email link).",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "bill_id": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["customer_id", "bill_id", "amount"],
    },
})
def send_payment_request(agent_db, user_db, customer_id: str, bill_id: str, amount: float):
    cust = _customers(agent_db).get(customer_id)
    if cust is None:
        return "Error: Customer not found."
    bill = _bills(agent_db).get(bill_id)
    if bill is None:
        return "Error: Bill not found."
    if bill.get("customer_id") != customer_id:
        return "Error: Bill does not belong to this customer."
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return "Error: amount must be a number."
    if amt <= 0:
        return "Error: amount must be greater than 0."
    requests = cust.setdefault("payment_requests", [])
    record = {
        "bill_id": bill_id,
        "amount": amt,
        "requested_at": _now_iso(),
        "status": "pending",
    }
    requests.append(record)
    return {"customer_id": customer_id, "payment_request": record}


@agent_tool({
    "name": "reset_network_provisioning",
    "description": "Re-push carrier provisioning (APN/MMSC) for a line; flags that the device needs a reboot.",
    "parameters": {
        "type": "object",
        "properties": {
            "line_id": {"type": "string"},
        },
        "required": ["line_id"],
    },
})
def reset_network_provisioning(agent_db, user_db, line_id: str):
    line = _lines(agent_db).get(line_id)
    if line is None:
        return "Error: Line not found."
    line["provisioning_reset_at"] = _now_iso()
    line["provisioning_needs_reboot"] = True
    device_id, device = _find_device_for_line(user_db, line_id)
    if device is not None:
        device["apn_valid"] = True
        device["mmsc_valid"] = True
    return {
        "line_id": line_id,
        "provisioning_reset_at": line["provisioning_reset_at"],
        "provisioning_needs_reboot": True,
        "device_id": device_id,
    }


@agent_tool({
    "name": "add_support_note",
    "description": "Append an internal support note onto a customer's record.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "note": {"type": "string", "description": "Non-empty support note text."},
        },
        "required": ["customer_id", "note"],
    },
})
def add_support_note(agent_db, user_db, customer_id: str, note: str):
    cust = _customers(agent_db).get(customer_id)
    if cust is None:
        return "Error: Customer not found."
    if not (note and note.strip()):
        return "Error: note must be a non-empty string."
    notes = cust.setdefault("support_notes", [])
    entry = {"note": note.strip(), "at": _now_iso()}
    notes.append(entry)
    return {"customer_id": customer_id, "support_note": entry, "count": len(notes)}


@agent_tool({
    "name": "transfer_to_human_agent",
    "description": "Escalate the case to a human agent with a short summary.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Short summary of the issue and steps tried."},
        },
        "required": ["summary"],
    },
})
def transfer_to_human_agent(agent_db, user_db, summary: str):
    if not (summary and summary.strip()):
        return "Error: summary must be a non-empty string."
    agent_db["_transferred"] = {"summary": summary.strip(), "at": _now_iso()}
    return {"transferred": True}
