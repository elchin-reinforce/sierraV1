"""Retail domain tool implementations."""
from __future__ import annotations
import ast
import operator
from typing import Any

from taufreebench.core.tool import tool


def _normalize_order_id(order_id: str) -> str:
    """Order IDs in the DB always start with '#'. Many models pass them without the prefix
    (e.g., 'W4082615' instead of '#W4082615'). Normalize so the lookup succeeds either way.
    The original τ-bench tool implementations are similarly lenient.
    """
    if not isinstance(order_id, str):
        return order_id
    order_id = order_id.strip()
    if order_id.startswith("#"):
        return order_id
    return "#" + order_id


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@tool(
    name="find_user_id_by_email",
    description="Find a user's ID by their email address. Use this to authenticate the user.",
    read_only=True,
    domain="retail",
)
def find_user_id_by_email(db: dict[str, Any], email: str) -> str:
    for uid, user in db["users"].items():
        if user.get("email", "").lower() == email.lower():
            return uid
    return "Error: No user found with that email address."


@tool(
    name="find_user_id_by_name_zip",
    description="Find a user's ID by their first name, last name, and ZIP code.",
    read_only=True,
    domain="retail",
)
def find_user_id_by_name_zip(db: dict[str, Any], first_name: str, last_name: str, zip: str) -> str:
    for uid, user in db["users"].items():
        if (
            user.get("first_name", "").lower() == first_name.lower()
            and user.get("last_name", "").lower() == last_name.lower()
            and user.get("address", {}).get("zip", "") == zip
        ):
            return uid
    return "Error: No user found with that name and ZIP code."


@tool(
    name="get_user_details",
    description="Get full profile details for a user including address and payment methods.",
    read_only=True,
    domain="retail",
)
def get_user_details(db: dict[str, Any], user_id: str) -> dict[str, Any]:
    user = db["users"].get(user_id)
    if user is None:
        return {"error": f"Error: User '{user_id}' not found."}
    return user


@tool(
    name="get_order_details",
    description="Get full details for an order including items, status, shipping address, and payment history.",
    read_only=True,
    domain="retail",
)
def get_order_details(db: dict[str, Any], order_id: str) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    return order


@tool(
    name="get_product_details",
    description="Get details for a product including all variants, prices, and availability.",
    read_only=True,
    domain="retail",
)
def get_product_details(db: dict[str, Any], product_id: str) -> dict[str, Any]:
    product = db["products"].get(product_id)
    if product is None:
        return {"error": f"Error: Product '{product_id}' not found."}
    return product


@tool(
    name="list_all_product_types",
    description="List all available product types and their product IDs.",
    read_only=True,
    domain="retail",
)
def list_all_product_types(db: dict[str, Any]) -> dict[str, Any]:
    return {
        pid: {"product_id": pid, "name": p["name"], "product_type": p["product_type"]}
        for pid, p in db["products"].items()
    }


@tool(
    name="calculate",
    description="Evaluate a simple arithmetic expression and return the result as a string.",
    read_only=True,
    domain="retail",
)
def calculate(db: dict[str, Any], expression: str) -> str:
    try:
        result = _safe_eval(expression)
        return str(round(result, 2))
    except Exception as e:
        return f"Error: Could not evaluate expression — {e}"


@tool(
    name="transfer_to_human_agents",
    description="Transfer the conversation to a human agent when the request cannot be handled by automated tools.",
    read_only=True,
    domain="retail",
)
def transfer_to_human_agents(db: dict[str, Any], summary: str) -> str:
    return f"Transferring to human agent. Summary: {summary}"


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@tool(
    name="cancel_pending_order",
    description="Cancel a pending order. Reason must be 'no longer needed' or 'ordered by mistake'.",
    read_only=False,
    domain="retail",
)
def cancel_pending_order(db: dict[str, Any], order_id: str, reason: str) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "pending":
        return {"error": f"Error: Order '{order_id}' has status '{order['status']}' and cannot be cancelled. Only pending orders can be cancelled."}
    valid_reasons = {"no longer needed", "ordered by mistake"}
    if reason not in valid_reasons:
        return {"error": f"Error: Invalid cancellation reason. Must be one of: {sorted(valid_reasons)}."}
    order["status"] = "cancelled"
    order["cancellation_reason"] = reason
    return {"order_id": order_id, "status": "cancelled", "cancellation_reason": reason}


@tool(
    name="modify_pending_order_address",
    description="Update the shipping address of a pending order.",
    read_only=False,
    domain="retail",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "address1": {"type": "string"},
            "address2": {"type": "string"},
            "city": {"type": "string"},
            "state": {"type": "string"},
            "country": {"type": "string"},
            "zip": {"type": "string"},
        },
        "required": ["order_id", "address1", "address2", "city", "state", "country", "zip"],
    },
)
def modify_pending_order_address(
    db: dict[str, Any],
    order_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "pending":
        return {"error": f"Error: Order '{order_id}' is not pending (status: '{order['status']}')."}
    order["shipping_address"] = {
        "address1": address1,
        "address2": address2,
        "city": city,
        "state": state,
        "country": country,
        "zip": zip,
    }
    return {"order_id": order_id, "shipping_address": order["shipping_address"]}


@tool(
    name="modify_user_address",
    description="Update the profile address of a user.",
    read_only=False,
    domain="retail",
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "address1": {"type": "string"},
            "address2": {"type": "string"},
            "city": {"type": "string"},
            "state": {"type": "string"},
            "country": {"type": "string"},
            "zip": {"type": "string"},
        },
        "required": ["user_id", "address1", "address2", "city", "state", "country", "zip"],
    },
)
def modify_user_address(
    db: dict[str, Any],
    user_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
) -> dict[str, Any]:
    user = db["users"].get(user_id)
    if user is None:
        return {"error": f"Error: User '{user_id}' not found."}
    user["address"] = {
        "address1": address1,
        "address2": address2,
        "city": city,
        "state": state,
        "country": country,
        "zip": zip,
    }
    return {"user_id": user_id, "address": user["address"]}


@tool(
    name="modify_pending_order_payment",
    description="Change the payment method for a pending order.",
    read_only=False,
    domain="retail",
)
def modify_pending_order_payment(
    db: dict[str, Any],
    order_id: str,
    payment_method_id: str,
) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "pending":
        return {"error": f"Error: Order '{order_id}' is not pending (status: '{order['status']}')."}
    user = db["users"].get(order["user_id"])
    if user is None or payment_method_id not in user.get("payment_methods", {}):
        return {"error": f"Error: Payment method '{payment_method_id}' not found in user's profile."}
    for entry in order["payment_history"]:
        entry["status"] = "refunded"
    order["payment_history"].append({
        "payment_method_id": payment_method_id,
        "amount": sum(i["price"] * i.get("quantity", 1) for i in order["items"]),
        "status": "charged",
    })
    return {"order_id": order_id, "payment_method_id": payment_method_id}


@tool(
    name="modify_pending_order_items",
    description=(
        "Swap items in a pending order. item_ids and new_item_ids must be the same length. "
        "Each new item must be a different variant of the same product type. "
        "This can only be called ONCE per order — collect all changes before calling."
    ),
    read_only=False,
    domain="retail",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "item_ids": {"type": "array", "items": {"type": "string"}},
            "new_item_ids": {"type": "array", "items": {"type": "string"}},
            "payment_method_id": {"type": "string"},
        },
        "required": ["order_id", "item_ids", "new_item_ids", "payment_method_id"],
    },
)
def modify_pending_order_items(
    db: dict[str, Any],
    order_id: str,
    item_ids: list[str],
    new_item_ids: list[str],
    payment_method_id: str,
) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "pending":
        return {"error": f"Error: Order '{order_id}' is not pending (status: '{order['status']}')."}
    if len(item_ids) != len(new_item_ids):
        return {"error": "Error: item_ids and new_item_ids must have the same length."}

    user = db["users"].get(order["user_id"])
    if user is None or payment_method_id not in user.get("payment_methods", {}):
        return {"error": f"Error: Payment method '{payment_method_id}' not found in user's profile."}

    order_item_ids = [i["item_id"] for i in order["items"]]
    for old_id in item_ids:
        if old_id not in order_item_ids:
            return {"error": f"Error: Item '{old_id}' not found in order."}

    all_variants = _all_variants(db)
    old_to_new = list(zip(item_ids, new_item_ids))
    price_diff = 0.0
    for old_id, new_id in old_to_new:
        old_variant = all_variants.get(old_id)
        new_variant = all_variants.get(new_id)
        if old_variant is None:
            return {"error": f"Error: Item variant '{old_id}' not found in product catalog."}
        if new_variant is None:
            return {"error": f"Error: Item variant '{new_id}' not found in product catalog."}
        if old_variant["product_id"] != new_variant["product_id"]:
            return {"error": f"Error: Cannot change product type. '{old_id}' and '{new_id}' belong to different products."}
        if not new_variant.get("available", False):
            return {"error": f"Error: Item '{new_id}' is not available."}
        price_diff += new_variant["price"] - old_variant["price"]

    for old_id, new_id in old_to_new:
        new_variant = all_variants[new_id]
        for item in order["items"]:
            if item["item_id"] == old_id:
                item["item_id"] = new_id
                item["name"] = new_variant["name"]
                item["price"] = new_variant["price"]
                break

    order["status"] = "pending (items modified)"
    price_diff = round(price_diff, 2)
    if price_diff > 0:
        order["payment_history"].append({
            "payment_method_id": payment_method_id,
            "amount": price_diff,
            "status": "charged",
        })
    elif price_diff < 0:
        order["payment_history"].append({
            "payment_method_id": payment_method_id,
            "amount": abs(price_diff),
            "status": "refunded",
        })
    return {"order_id": order_id, "status": order["status"], "price_difference": price_diff}


@tool(
    name="return_delivered_order_items",
    description=(
        "Return items from a delivered order. The refund goes to payment_method_id, "
        "which must be the original payment method or an existing gift card."
    ),
    read_only=False,
    domain="retail",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "item_ids": {"type": "array", "items": {"type": "string"}},
            "payment_method_id": {"type": "string"},
        },
        "required": ["order_id", "item_ids", "payment_method_id"],
    },
)
def return_delivered_order_items(
    db: dict[str, Any],
    order_id: str,
    item_ids: list[str],
    payment_method_id: str,
) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "delivered":
        return {"error": f"Error: Order '{order_id}' has status '{order['status']}'. Only delivered orders can be returned."}

    user = db["users"].get(order["user_id"])
    original_pm_ids = {e["payment_method_id"] for e in order["payment_history"]}
    user_pms = set(user.get("payment_methods", {}).keys()) if user else set()
    gift_cards = {
        pid for pid, pm in (user.get("payment_methods", {}) if user else {}).items()
        if pm.get("type") == "gift_card"
    }
    if payment_method_id not in original_pm_ids and payment_method_id not in gift_cards:
        return {"error": f"Error: Refund payment method '{payment_method_id}' must be the original payment method or an existing gift card."}

    order_item_ids = [i["item_id"] for i in order["items"]]
    for iid in item_ids:
        if iid not in order_item_ids:
            return {"error": f"Error: Item '{iid}' not found in order."}

    refund_amount = round(
        sum(i["price"] * i.get("quantity", 1) for i in order["items"] if i["item_id"] in item_ids),
        2,
    )
    order["status"] = "return requested"
    order["return_items"] = item_ids
    order["return_payment_method_id"] = payment_method_id
    order["refund_amount"] = refund_amount
    return {
        "order_id": order_id,
        "status": "return requested",
        "return_items": item_ids,
        "refund_amount": refund_amount,
        "payment_method_id": payment_method_id,
    }


@tool(
    name="exchange_delivered_order_items",
    description=(
        "Exchange items from a delivered order. item_ids and new_item_ids must be the same length "
        "and new items must be the same product type (different variant). "
        "Call ONCE with all exchange pairs collected."
    ),
    read_only=False,
    domain="retail",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "item_ids": {"type": "array", "items": {"type": "string"}},
            "new_item_ids": {"type": "array", "items": {"type": "string"}},
            "payment_method_id": {"type": "string"},
        },
        "required": ["order_id", "item_ids", "new_item_ids", "payment_method_id"],
    },
)
def exchange_delivered_order_items(
    db: dict[str, Any],
    order_id: str,
    item_ids: list[str],
    new_item_ids: list[str],
    payment_method_id: str,
) -> dict[str, Any]:
    order_id = _normalize_order_id(order_id)
    order = db["orders"].get(order_id)
    if order is None:
        return {"error": f"Error: Order '{order_id}' not found."}
    if order["status"] != "delivered":
        return {"error": f"Error: Order '{order_id}' has status '{order['status']}'. Only delivered orders can be exchanged."}
    if len(item_ids) != len(new_item_ids):
        return {"error": "Error: item_ids and new_item_ids must have the same length."}

    user = db["users"].get(order["user_id"])
    if user is None or payment_method_id not in user.get("payment_methods", {}):
        return {"error": f"Error: Payment method '{payment_method_id}' not found in user's profile."}

    order_item_ids = [i["item_id"] for i in order["items"]]
    for iid in item_ids:
        if iid not in order_item_ids:
            return {"error": f"Error: Item '{iid}' not found in order."}

    all_variants = _all_variants(db)
    price_diff = 0.0
    for old_id, new_id in zip(item_ids, new_item_ids):
        old_v = all_variants.get(old_id)
        new_v = all_variants.get(new_id)
        if old_v is None:
            return {"error": f"Error: Item '{old_id}' not found in product catalog."}
        if new_v is None:
            return {"error": f"Error: Item '{new_id}' not found in product catalog."}
        if old_v["product_id"] != new_v["product_id"]:
            return {"error": f"Error: Cannot change product type during exchange."}
        if not new_v.get("available", True):
            return {"error": f"Error: Item '{new_id}' is not available."}
        price_diff += new_v["price"] - old_v["price"]

    price_diff = round(price_diff, 2)
    order["status"] = "exchange requested"
    order["exchange_items"] = item_ids
    order["exchange_new_items"] = new_item_ids
    order["exchange_payment_method_id"] = payment_method_id
    order["exchange_price_difference"] = price_diff
    return {
        "order_id": order_id,
        "status": "exchange requested",
        "exchange_items": item_ids,
        "exchange_new_items": new_item_ids,
        "exchange_price_difference": price_diff,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_variants(db: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for product in db["products"].values():
        for vid, variant in product.get("variants", {}).items():
            result[vid] = variant
    return result


def _safe_eval(expr: str) -> float:
    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
    }

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in allowed_ops:
                raise ValueError(f"Unsupported operator: {op_type}")
            return allowed_ops[op_type](_eval_node(node.left), _eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval_node(node.operand)
        raise ValueError(f"Unsupported expression node: {type(node)}")

    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)
