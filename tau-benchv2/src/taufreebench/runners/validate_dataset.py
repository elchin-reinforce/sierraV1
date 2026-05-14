"""Validate dataset integrity: replay expected actions and check references."""
from __future__ import annotations
import copy
import re
from pathlib import Path
from typing import Any

from taufreebench.core.db import load_domain_db
from taufreebench.core.tool import get_domain_tools
from taufreebench.runners.run_episode import _get_data_dir, _load_tasks


def validate_dataset(domain: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Validate every task in a domain. Returns a list of {task_id, status, error}."""
    # Ensure domain tools registered
    if domain == "retail":
        import taufreebench.domains.retail.tools  # noqa: F401

    base = _get_data_dir(domain, data_dir)
    db = load_domain_db(domain, base)
    tasks = _load_tasks(domain, base)
    tools = get_domain_tools(domain)

    user_ids = set(db.get("users", {}).keys())
    order_ids = set(db.get("orders", {}).keys())
    product_ids = set(db.get("products", {}).keys())
    item_ids: set[str] = set()
    for product in db.get("products", {}).values():
        item_ids.update(product.get("variants", {}).keys())
    payment_method_ids: set[str] = set()
    for user in db.get("users", {}).values():
        payment_method_ids.update(user.get("payment_methods", {}).keys())

    results: list[dict[str, Any]] = []
    for task in tasks:
        errors: list[str] = []

        # 1. required_outputs must be strings
        for ro in task.required_outputs:
            if not isinstance(ro, str):
                errors.append(f"required_outputs entry not a string: {ro!r}")

        # 2. Reference checks on expected_actions arguments
        for action in task.expected_actions:
            args = action.arguments
            if "user_id" in args and args["user_id"] not in user_ids:
                errors.append(f"action {action.name} references unknown user_id={args['user_id']}")
            if "order_id" in args and args["order_id"] not in order_ids:
                errors.append(f"action {action.name} references unknown order_id={args['order_id']}")
            if "product_id" in args and args["product_id"] not in product_ids:
                errors.append(f"action {action.name} references unknown product_id={args['product_id']}")
            if "payment_method_id" in args and args["payment_method_id"] not in payment_method_ids:
                errors.append(f"action {action.name} references unknown payment_method_id={args['payment_method_id']}")
            for key in ("item_ids", "new_item_ids"):
                ids = args.get(key) or []
                if isinstance(ids, list):
                    for iid in ids:
                        if iid not in item_ids:
                            errors.append(f"action {action.name} references unknown item_id={iid}")

        # 3. Replay expected_actions on fresh DB; ensure no tool returns Error
        replay_db = copy.deepcopy(db)
        for action in task.expected_actions:
            tool = tools.get(action.name)
            if tool is None:
                errors.append(f"action {action.name} — tool not registered")
                continue
            try:
                result = tool(replay_db, **action.arguments)
            except TypeError as e:
                errors.append(f"action {action.name} — bad arguments: {e}")
                continue
            except Exception as e:
                errors.append(f"action {action.name} — execution error: {e}")
                continue
            err_str = _extract_error(result)
            if err_str:
                errors.append(f"action {action.name} — tool returned error: {err_str}")

        # 4. Instruction references — verify any #W\d+ in instruction exists
        for m in re.findall(r"#W\d+", task.instruction):
            if m not in order_ids:
                errors.append(f"instruction references unknown order_id={m}")

        status = "ok" if not errors else "invalid"
        results.append({"task_id": task.id, "status": status, "errors": errors})

    return results


def _extract_error(result: Any) -> str | None:
    if isinstance(result, dict) and "error" in result:
        return str(result["error"])
    if isinstance(result, str) and result.startswith("Error:"):
        return result
    return None
