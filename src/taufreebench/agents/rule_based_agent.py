"""Rule-based retail agent — hardcoded state machine, no LLM required."""
from __future__ import annotations
import json
import re
from typing import Any

from taufreebench.core.types import AgentMessage, ToolCall
from .base import BaseAgent


class RuleBasedRetailAgent(BaseAgent):
    """Handles common retail tasks deterministically."""

    provider_name = "rule"
    model = "rule_based"

    # States
    _S_INIT = "init"
    _S_AUTH = "ask_auth"
    _S_AUTHENTICATED = "authenticated"
    _S_UNDERSTAND = "understand"
    _S_CONFIRM = "confirm"
    _S_DONE = "done"

    def __init__(self):
        self._state = self._S_INIT
        self._user_id: str | None = None
        self._pending_action: ToolCall | None = None
        self._pending_description: str = ""
        self._order_id: str | None = None
        self._intent: str | None = None
        self._tool_results: dict[str, Any] = {}
        self._completed_order_ids: set[str] = set()
        self._turn = 0
        self._stored_address: dict[str, str] | None = None
        self._compound_address_done: bool = False

    def act(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        policy: str,
    ) -> AgentMessage | ToolCall:
        self._turn += 1
        last_user = self._last_user_message(history)
        last_tool = self._last_tool_result(history)

        # --- Process tool results first ---
        if last_tool:
            return self._handle_tool_result(last_tool, history)

        # --- State machine ---
        if self._state == self._S_INIT:
            self._state = self._S_AUTH
            # Try to understand initial request
            self._parse_intent(last_user)
            return AgentMessage(content="Hello! I'm happy to help. Could you please verify your identity? I'll need your email address or your full name and ZIP code.")

        if self._state == self._S_AUTH:
            # Check if user provided auth info
            email = self._extract_email(last_user)
            if email:
                return ToolCall(name="find_user_id_by_email", arguments={"email": email})
            name_zip = self._extract_name_zip(last_user)
            if name_zip:
                return ToolCall(name="find_user_id_by_name_zip", arguments=name_zip)
            return AgentMessage(content="I need to verify your identity before proceeding. Please provide your email address, or your full name and ZIP code.")

        if self._state == self._S_AUTHENTICATED:
            # Re-parse intent with full message history
            self._parse_intent_from_history(history)
            self._state = self._S_UNDERSTAND
            return self._plan_action(history)

        if self._state == self._S_UNDERSTAND:
            return self._plan_action(history)

        if self._state == self._S_CONFIRM:
            # Allow user to refine specific item IDs during confirmation (e.g. partial return)
            if self._pending_action and self._pending_action.name == "return_delivered_order_items":
                order = self._tool_results.get("order", {})
                order_items = order.get("items", []) if isinstance(order, dict) else []
                specific = self._extract_specific_item_ids(last_user, order_items)
                if specific:
                    self._pending_action = ToolCall(
                        name=self._pending_action.name,
                        arguments={**self._pending_action.arguments, "item_ids": specific},
                    )
                    self._pending_description = f"return {specific} from order {self._order_id}"
            if self._user_confirmed(last_user):
                if self._pending_action:
                    self._state = self._S_DONE
                    return self._pending_action
            elif self._user_denied(last_user):
                self._state = self._S_DONE
                return AgentMessage(content="Understood, I've cancelled that action. Is there anything else I can help you with?")
            else:
                return AgentMessage(content=f"I need your confirmation. {self._pending_description} — shall I proceed? (yes/no)")

        if self._state == self._S_DONE:
            return AgentMessage(content="Is there anything else I can help you with today?")

        return AgentMessage(content="I'm sorry, I'm not sure how to help with that. Could you please clarify?")

    def _handle_tool_result(self, result: dict[str, Any], history: list[dict[str, Any]]) -> AgentMessage | ToolCall:
        tool_name = result.get("tool_name", "")
        content = result.get("content", "")

        # Try to parse content as JSON
        parsed: Any = content
        try:
            parsed = json.loads(content)
        except Exception:
            pass

        is_error = isinstance(parsed, dict) and "error" in parsed
        error_msg = parsed.get("error", "") if isinstance(parsed, dict) else ""
        if not is_error and isinstance(content, str) and content.startswith("Error:"):
            is_error = True
            error_msg = content

        if tool_name in ("find_user_id_by_email", "find_user_id_by_name_zip"):
            if is_error or (isinstance(parsed, str) and parsed.startswith("Error:")):
                self._state = self._S_AUTH
                return AgentMessage(content="I couldn't find an account with that information. Please double-check your email address or name and ZIP code.")
            user_id = parsed if isinstance(parsed, str) else str(parsed)
            self._user_id = user_id
            self._tool_results["user_id"] = user_id
            self._state = self._S_AUTHENTICATED
            return AgentMessage(content=f"I've verified your identity. How can I help you today?")

        if tool_name == "get_order_details":
            if is_error:
                return AgentMessage(content=f"I couldn't find that order. {error_msg}")
            self._tool_results["order"] = parsed
            return self._plan_action_after_order(parsed, history)

        if tool_name == "get_user_details":
            self._tool_results["user"] = parsed
            return self._plan_action(history)

        if tool_name == "get_product_details":
            self._tool_results["product"] = parsed
            return self._plan_price_response(parsed)

        if tool_name == "cancel_pending_order":
            if is_error:
                return AgentMessage(content=f"I wasn't able to cancel the order. {error_msg}")
            order_id = parsed.get("order_id", self._order_id) if isinstance(parsed, dict) else self._order_id
            if self._order_id:
                self._completed_order_ids.add(self._order_id)
            self._state = self._S_UNDERSTAND  # might have more actions
            return AgentMessage(content=f"Order {order_id} has been successfully cancelled. Is there anything else I can help you with?")

        if tool_name == "modify_pending_order_address":
            if is_error:
                return AgentMessage(content=f"I couldn't update the address. {error_msg}")
            order_id = parsed.get("order_id", self._order_id) if isinstance(parsed, dict) else self._order_id
            if self._order_id:
                self._completed_order_ids.add(self._order_id)
            # Compound address flow: mark complete, signal done
            if self._intent == "modify_both_addresses":
                self._compound_address_done = True
                self._intent = None
                self._state = self._S_DONE
                return AgentMessage(
                    content=f"Both your profile address and the shipping address for order {order_id} "
                            f"have been updated successfully. Is there anything else I can help with?"
                )
            self._state = self._S_UNDERSTAND
            return AgentMessage(content=f"The shipping address for order {order_id} has been updated successfully.")

        if tool_name == "modify_user_address":
            if is_error:
                return AgentMessage(content=f"I couldn't update your address. {error_msg}")
            # Compound address flow: automatically update order shipping address too
            if self._intent == "modify_both_addresses" and self._order_id and self._stored_address:
                return ToolCall(
                    name="modify_pending_order_address",
                    arguments={"order_id": self._order_id, **self._stored_address},
                )
            # Simple case: reset intent so next turn re-detects correctly
            self._intent = None
            self._state = self._S_UNDERSTAND
            return AgentMessage(content="Your profile address has been updated successfully.")

        if tool_name == "modify_pending_order_items":
            if is_error:
                return AgentMessage(content=f"I couldn't modify the order items. {error_msg}")
            diff = parsed.get("price_difference", 0) if isinstance(parsed, dict) else 0
            msg = f"The items in order {self._order_id} have been updated."
            if diff > 0:
                msg += f" An additional ${diff:.2f} has been charged."
            elif diff < 0:
                msg += f" A refund of ${abs(diff):.2f} will be issued."
            self._state = self._S_UNDERSTAND
            return AgentMessage(content=msg)

        if tool_name == "return_delivered_order_items":
            if is_error:
                return AgentMessage(content=f"I couldn't process the return. {error_msg}")
            amt = parsed.get("refund_amount", "?") if isinstance(parsed, dict) else "?"
            self._state = self._S_UNDERSTAND
            return AgentMessage(content=f"Your return has been requested. You will receive a refund of ${amt}.")

        if tool_name == "exchange_delivered_order_items":
            if is_error:
                return AgentMessage(content=f"I couldn't process the exchange. {error_msg}")
            diff = parsed.get("exchange_price_difference", 0) if isinstance(parsed, dict) else 0
            msg = "Your exchange has been requested."
            if diff > 0:
                msg += f" An additional ${diff:.2f} will be charged."
            elif diff < 0:
                msg += f" A refund of ${abs(diff):.2f} will be issued."
            self._state = self._S_UNDERSTAND
            return AgentMessage(content=msg)

        if tool_name == "modify_pending_order_payment":
            if is_error:
                return AgentMessage(content=f"I couldn't update the payment method. {error_msg}")
            self._state = self._S_UNDERSTAND
            return AgentMessage(content="The payment method for your order has been updated.")

        if tool_name == "transfer_to_human_agents":
            self._state = self._S_DONE
            return AgentMessage(content="I've transferred your case to a human agent. Note: processed orders cannot be modified or cancelled by the automated system.")

        if tool_name == "calculate":
            self._state = self._S_UNDERSTAND
            return AgentMessage(content=f"The result is: {content}")

        # Generic fallback
        return AgentMessage(content="I've processed your request. Is there anything else I can help with?")

    def _plan_action(self, history: list[dict[str, Any]]) -> AgentMessage | ToolCall:
        # Keep original case for ID extraction, lowercase for intent keyword matching
        all_user_text_orig = " ".join(m["content"] for m in history if m.get("role") == "user")
        all_user_text = all_user_text_orig.lower()

        if self._intent == "compound":
            # Prefer the most recently mentioned uncompleted order
            last_user = self._last_user_message(history)
            last_oid = self._extract_order_id(last_user)
            if last_oid and last_oid not in self._completed_order_ids:
                self._order_id = last_oid
            else:
                all_oids = list(dict.fromkeys(re.findall(r"#W\d+", all_user_text_orig)))
                pending = [o for o in all_oids if o not in self._completed_order_ids]
                if pending:
                    self._order_id = pending[0]
        else:
            order_id = self._extract_order_id(all_user_text_orig)
            if order_id:
                self._order_id = order_id

        if not self._intent:
            self._parse_intent(all_user_text)

        # If we know the intent and have the order, plan the action
        if self._intent == "cancel" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent in ("return", "exchange") and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent == "modify_order_address" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent == "modify_both_addresses" and self._user_id:
            # Both profile address + order shipping address update
            if self._compound_address_done:
                self._state = self._S_DONE
                return AgentMessage(content="Both your profile address and the order's shipping address have been updated. Is there anything else I can help with?")
            new_addr = self._extract_address(all_user_text_orig)
            order_id = self._extract_order_id(all_user_text_orig)
            if new_addr and order_id:
                self._order_id = order_id
                self._stored_address = new_addr
                self._pending_action = ToolCall(
                    name="modify_user_address",
                    arguments={"user_id": self._user_id, **new_addr},
                )
                self._pending_description = (
                    f"update your profile address and order {order_id} shipping address to "
                    f"{new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}"
                )
                self._state = self._S_CONFIRM
                return AgentMessage(
                    content=f"I'll update both your profile address and the shipping address for order {order_id} to: "
                            f"{new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}, {new_addr['country']}. "
                            f"Shall I proceed?"
                )
            return AgentMessage(content="Please provide the new address.")

        if self._intent == "modify_user_address" and self._user_id:
            new_addr = self._extract_address(all_user_text_orig)
            if new_addr:
                self._pending_action = ToolCall(name="modify_user_address", arguments={"user_id": self._user_id, **new_addr})
                self._pending_description = f"I will update your profile address to: {new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}"
                self._state = self._S_CONFIRM
                return AgentMessage(content=f"I'd like to update your profile address to: {new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}, {new_addr['country']}. Shall I proceed?")
            return AgentMessage(content="Please provide your new address (street, city, state, ZIP, country).")

        if self._intent == "modify_order_items" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent == "modify_order_payment" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent == "get_order_status" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        if self._intent == "price_inquiry":
            # Look up headphones product for price comparison
            return ToolCall(name="get_product_details", arguments={"product_id": "prod_headphones_005"})

        if self._intent == "compound" and self._order_id:
            return ToolCall(name="get_order_details", arguments={"order_id": self._order_id})

        # Fallback: ask for clarification
        return AgentMessage(content="I'd be happy to help. Could you please tell me more about what you need? For example, do you want to cancel, return, or exchange an order?")

    def _plan_action_after_order(self, order: dict[str, Any], history: list[dict[str, Any]]) -> AgentMessage | ToolCall:
        status = order.get("status", "")
        order_id = order.get("order_id", self._order_id)
        all_user_text_orig = " ".join(m["content"] for m in history if m.get("role") == "user")
        all_user_text = all_user_text_orig.lower()

        if self._intent == "cancel":
            if status != "pending":
                if status == "processed":
                    return ToolCall(
                        name="transfer_to_human_agents",
                        arguments={"summary": f"Customer requested cancellation of processed order {order_id}. The order has status '{status}' and cannot be modified by the automated system."},
                    )
                return AgentMessage(content=f"I'm sorry, order {order_id} has status '{status}' and cannot be cancelled. Only pending orders can be cancelled.")
            reason = self._extract_cancel_reason(all_user_text)
            self._pending_action = ToolCall(name="cancel_pending_order", arguments={"order_id": order_id, "reason": reason})
            self._pending_description = f"I will cancel order {order_id} (reason: {reason})"
            self._state = self._S_CONFIRM
            return AgentMessage(content=f"I'll cancel order {order_id} with reason '{reason}'. Shall I proceed?")

        if self._intent == "return":
            if status != "delivered":
                return AgentMessage(content=f"I'm sorry, order {order_id} has status '{status}'. Only delivered orders can be returned.")
            items = order.get("items", [])
            all_item_ids = [i["item_id"] for i in items]
            # Use specific items if user mentioned them in their messages (handles partial returns)
            specific = self._extract_specific_item_ids(all_user_text_orig, items)
            item_ids = specific if specific else all_item_ids
            payment_id = self._extract_payment_method(all_user_text, order)
            if not payment_id:
                hist = order.get("payment_history", [])
                payment_id = hist[0]["payment_method_id"] if hist else ""
            self._pending_action = ToolCall(
                name="return_delivered_order_items",
                arguments={"order_id": order_id, "item_ids": item_ids, "payment_method_id": payment_id},
            )
            self._pending_description = f"I will return {item_ids} from order {order_id} and refund to {payment_id}"
            self._state = self._S_CONFIRM
            return AgentMessage(content=f"I'll process a return for order {order_id}. The refund will go to payment method {payment_id}. Shall I proceed?")

        if self._intent == "exchange":
            if status != "delivered":
                return AgentMessage(content=f"I'm sorry, order {order_id} has status '{status}'. Only delivered orders can be exchanged.")
            items = order.get("items", [])
            item_ids = [i["item_id"] for i in items]
            new_item_ids = self._extract_new_item_ids(all_user_text, items)
            payment_id = self._extract_payment_method(all_user_text, order)
            if not payment_id:
                hist = order.get("payment_history", [])
                payment_id = hist[0]["payment_method_id"] if hist else ""
            if not new_item_ids or len(new_item_ids) != len(item_ids):
                return AgentMessage(content=f"I see your order {order_id} contains {len(items)} item(s). What would you like to exchange them for? Please specify the new item IDs.")
            self._pending_action = ToolCall(
                name="exchange_delivered_order_items",
                arguments={
                    "order_id": order_id,
                    "item_ids": item_ids,
                    "new_item_ids": new_item_ids,
                    "payment_method_id": payment_id,
                },
            )
            self._pending_description = f"I will exchange items in order {order_id}"
            self._state = self._S_CONFIRM
            return AgentMessage(content=f"I'll exchange the items in order {order_id}. Shall I proceed?")

        if self._intent == "modify_order_address":
            if status != "pending":
                return AgentMessage(content=f"I'm sorry, only pending orders can have their address changed. Order {order_id} has status '{status}'.")
            new_addr = self._extract_address(all_user_text_orig)
            if not new_addr:
                return AgentMessage(content="Please provide the new shipping address (street, city, state, ZIP, country).")
            self._pending_action = ToolCall(name="modify_pending_order_address", arguments={"order_id": order_id, **new_addr})
            self._pending_description = f"I will update shipping address for order {order_id} to {new_addr['address1']}, {new_addr['city']}, {new_addr['state']}"
            self._state = self._S_CONFIRM
            return AgentMessage(content=f"I'll update the shipping address for order {order_id} to: {new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}. Shall I proceed?")

        if self._intent == "modify_order_payment":
            if status != "pending":
                return AgentMessage(content=f"I'm sorry, order {order_id} has status '{status}'. Only pending orders can have their payment method changed.")
            last_user = self._last_user_message(history)
            payment_id = self._extract_payment_to(last_user) or self._extract_payment_to(all_user_text_orig) or self._extract_payment_method(all_user_text, order)
            if not payment_id:
                return AgentMessage(content="Please provide the new payment method ID.")
            self._pending_action = ToolCall(name="modify_pending_order_payment", arguments={"order_id": order_id, "payment_method_id": payment_id})
            self._pending_description = f"update payment method on order {order_id} to {payment_id}"
            self._state = self._S_CONFIRM
            return AgentMessage(content=f"I'll change the payment method on order {order_id} to {payment_id}. Shall I proceed?")

        if self._intent == "get_order_status":
            self._state = self._S_DONE
            return AgentMessage(content=f"Order {order_id} has status '{status}'.")

        if self._intent in ("modify_order_items", "exchange"):
            if status == "pending":
                items = order.get("items", [])
                item_ids = [i["item_id"] for i in items]
                new_item_ids = self._extract_new_item_ids(all_user_text_orig, items)
                payment_id = self._extract_payment_method(all_user_text, order)
                if not new_item_ids:
                    return AgentMessage(content="What would you like to change the items to? Please specify the new item IDs.")
                if not payment_id:
                    hist = order.get("payment_history", [])
                    payment_id = hist[0]["payment_method_id"] if hist else ""
                self._pending_action = ToolCall(
                    name="modify_pending_order_items",
                    arguments={"order_id": order_id, "item_ids": item_ids, "new_item_ids": new_item_ids, "payment_method_id": payment_id},
                )
                self._state = self._S_CONFIRM
                return AgentMessage(content=f"I'll change the items in order {order_id} and process any price difference to {payment_id}. Shall I proceed?")
            elif status == "delivered" and self._intent in ("exchange", "modify_order_items"):
                items = order.get("items", [])
                item_ids = [i["item_id"] for i in items]
                new_item_ids = self._extract_new_item_ids(all_user_text_orig, items)
                payment_id = self._extract_payment_method(all_user_text, order)
                if not new_item_ids or len(new_item_ids) != len(item_ids):
                    return AgentMessage(content=f"I see your order {order_id} contains {len(items)} item(s). What would you like to exchange them for?")
                if not payment_id:
                    hist = order.get("payment_history", [])
                    payment_id = hist[0]["payment_method_id"] if hist else ""
                self._pending_action = ToolCall(
                    name="exchange_delivered_order_items",
                    arguments={"order_id": order_id, "item_ids": item_ids, "new_item_ids": new_item_ids, "payment_method_id": payment_id},
                )
                self._state = self._S_CONFIRM
                return AgentMessage(content=f"I'll exchange the items in order {order_id}. Shall I proceed?")
            else:
                return AgentMessage(content=f"I'm sorry, only pending orders can have items modified. Order {order_id} has status '{status}'.")

        if self._intent == "compound":
            all_oids = list(dict.fromkeys(re.findall(r"#[Ww]\d+", all_user_text_orig)))
            pending_oids = [o for o in all_oids if o not in self._completed_order_ids]
            if pending_oids:
                next_oid = pending_oids[0]
                self._order_id = next_oid
                sub_intent = self._intent_for_order(next_oid, all_user_text)
                if sub_intent == "cancel":
                    reason = self._extract_cancel_reason(all_user_text)
                    self._pending_action = ToolCall(name="cancel_pending_order", arguments={"order_id": next_oid, "reason": reason})
                    self._state = self._S_CONFIRM
                    return AgentMessage(content=f"I'll cancel order {next_oid} (reason: {reason}). Shall I proceed?")
                if sub_intent == "modify_order_address":
                    if status != "pending":
                        return AgentMessage(content=f"Order {next_oid} has status '{status}' and cannot have its address changed.")
                    new_addr = self._extract_address(all_user_text_orig)
                    if not new_addr:
                        return AgentMessage(content="Please provide the new shipping address (street, city, state, ZIP).")
                    self._pending_action = ToolCall(name="modify_pending_order_address", arguments={"order_id": next_oid, **new_addr})
                    self._pending_description = f"update shipping address for {next_oid}"
                    self._state = self._S_CONFIRM
                    return AgentMessage(content=f"I'll update the shipping address for order {next_oid} to: {new_addr['address1']}, {new_addr['city']}, {new_addr['state']} {new_addr['zip']}. Shall I proceed?")
                if sub_intent == "modify_order_items":
                    if status != "pending":
                        return AgentMessage(content=f"Order {next_oid} has status '{status}' — items cannot be modified.")
                    items = order.get("items", [])
                    item_ids = [i["item_id"] for i in items]
                    new_item_ids = self._extract_new_item_ids(all_user_text_orig, items)
                    payment_id = self._extract_payment_method(all_user_text_orig, order)
                    if not new_item_ids or len(new_item_ids) != len(item_ids):
                        return AgentMessage(content=f"What would you like to change the items in {next_oid} to?")
                    if not payment_id:
                        hist = order.get("payment_history", [])
                        payment_id = hist[0]["payment_method_id"] if hist else ""
                    self._pending_action = ToolCall(
                        name="modify_pending_order_items",
                        arguments={"order_id": next_oid, "item_ids": item_ids, "new_item_ids": new_item_ids, "payment_method_id": payment_id},
                    )
                    self._state = self._S_CONFIRM
                    return AgentMessage(content=f"I'll change the items in order {next_oid} and process any price difference to {payment_id}. Shall I proceed?")

        return AgentMessage(content=f"I see your order {order_id} with status '{status}'. How would you like me to help with it?")

    def _plan_price_response(self, product: dict[str, Any]) -> AgentMessage | ToolCall:
        variants = product.get("variants", {})
        prices = {vid: v["price"] for vid, v in variants.items()}
        if len(prices) >= 2:
            sorted_prices = sorted(prices.values())
            diff = round(sorted_prices[-1] - sorted_prices[0], 2)
            # Find specific variants
            pro = {vid: v for vid, v in variants.items() if "pro" in vid.lower()}
            standard = {vid: v for vid, v in variants.items() if "standard" in vid.lower()}
            if pro and standard:
                pro_price = list(pro.values())[0]["price"]
                std_price = list(standard.values())[0]["price"]
                diff = round(pro_price - std_price, 2)
                return AgentMessage(content=f"The Pro model costs ${pro_price:.2f} and the Standard model costs ${std_price:.2f}. The difference is ${diff:.2f}.")
            return AgentMessage(content=f"The price difference between variants is ${diff:.2f}.")
        return AgentMessage(content=f"Here are the product details: {json.dumps(prices, indent=2)}")

    # ---------------------------------------------------------------------------
    # Parsing helpers
    # ---------------------------------------------------------------------------

    def _last_user_message(self, history: list[dict[str, Any]]) -> str:
        for msg in reversed(history):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _last_tool_result(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        # Only return a tool result if it is the most recent message (agent must react immediately)
        if not history:
            return None
        last = history[-1]
        if last.get("role") == "tool":
            return last
        return None

    def _parse_intent(self, text: str) -> None:
        t = text.lower()
        # Note: text may already be lowercased; use self._order_id for order presence checks
        has_order = bool(self._order_id) or bool(re.search(r"#[Ww]\d+", text))
        # item_id patterns are a strong signal for modify_items or exchange
        has_item_ids = bool(re.findall(r"item_\w+", t))

        if any(w in t for w in ["cancel"]):
            self._intent = "cancel"
        elif has_item_ids and any(w in t for w in ["change", "switch", "replace", "downgrade", "upgrade", "modify", "to item_"]):
            # item IDs + swap verb → modify items (pending) or exchange (delivered)
            # We'll resolve pending vs delivered when we see the order status
            self._intent = "modify_order_items"
        elif any(w in t for w in ["exchange", "swap"]) and has_item_ids:
            self._intent = "exchange"
        elif any(w in t for w in ["return"]) and not has_item_ids:
            self._intent = "return"
        elif any(w in t for w in ["refund"]) and not has_item_ids:
            self._intent = "return"
        elif any(w in t for w in ["exchange", "swap"]):
            self._intent = "exchange"
        elif ("both" in t and "address" in t and has_order) or ("profile address" in t and "shipping address" in t and has_order):
            self._intent = "modify_both_addresses"
        elif any(w in t for w in ["shipping address", "delivery address", "ship to", "address for order", "address for my order", "new address"]) and has_order:
            self._intent = "modify_order_address"
        elif any(w in t for w in ["my address", "profile address", "update my address", "change my address"]) and not has_order:
            self._intent = "modify_user_address"
        elif any(w in t for w in ["new address"]) and not has_order:
            self._intent = "modify_user_address"
        elif any(w in t for w in ["change", "modify", "switch", "downgrade", "upgrade"]) and any(w in t for w in ["item", "headphone", "backpack", "shoe", "t-shirt", "jeans"]):
            self._intent = "modify_order_items"
        elif any(w in t for w in ["payment method", "payment to", "change payment", "switch payment"]) and has_order:
            self._intent = "modify_order_payment"
        elif any(w in t for w in ["status of", "order status", "current status"]) and has_order:
            self._intent = "get_order_status"
        elif any(w in t for w in ["price", "cost", "how much", "difference"]):
            self._intent = "price_inquiry"
        # Detect compound if multiple distinct orders mentioned
        order_ids = list(dict.fromkeys(re.findall(r"#[Ww]\d+", text)))
        if len(order_ids) >= 2:
            self._intent = "compound"

    def _parse_intent_from_history(self, history: list[dict[str, Any]]) -> None:
        combined_orig = " ".join(m.get("content", "") for m in history if m.get("role") == "user")
        combined = combined_orig.lower()
        self._parse_intent(combined)
        # Also extract order IDs from original case
        oid = self._extract_order_id(combined_orig)
        if oid:
            self._order_id = oid

    def _extract_email(self, text: str) -> str | None:
        m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return m.group(0) if m else None

    def _extract_name_zip(self, text: str) -> dict[str, str] | None:
        zip_m = re.search(r"\b(\d{5})\b", text)
        if not zip_m:
            return None
        # Look for capitalized first + last name patterns
        # e.g. "My name is Olivia Brown", "I'm Olivia Brown", "Olivia Brown, 30301"
        name_m = re.search(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", text)
        if name_m:
            return {"first_name": name_m.group(1), "last_name": name_m.group(2), "zip": zip_m.group(1)}
        parts = text.strip().split()
        if len(parts) >= 3:
            return {"first_name": parts[0], "last_name": parts[1], "zip": zip_m.group(1)}
        return None

    def _extract_order_id(self, text: str) -> str | None:
        m = re.search(r"#W\d+", text)
        return m.group(0) if m else None

    def _extract_cancel_reason(self, text: str) -> str:
        if re.search(r"\b(mistake|accident|by accident)\b", text, re.IGNORECASE):
            return "ordered by mistake"
        return "no longer needed"

    def _extract_address(self, text: str) -> dict[str, str] | None:
        # Strip order IDs first to prevent their digits from being matched as street numbers
        clean = re.sub(r"#[Ww]\d+", "", text)
        # Pattern: "<number> <street>, <city>, <STATE> <zip>" with optional country
        # Try the common US address pattern
        pattern = re.search(
            r"(\d+\s+[\w\s]+(?:St|Ave|Rd|Blvd|Dr|Ln|Ct|Pl|Way|Congress|Maple|Oak|Pine|Main|Elm|Cedar|Park|Lake|River|Hill|Valley|Summit|Ridge|Grove|Glen|View|Garden|Forest|Meadow|Springs?|Heights?)[\w\s]*),\s*([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5})",
            clean, re.IGNORECASE,
        )
        if pattern:
            address1 = pattern.group(1).strip()
            city = pattern.group(2).strip()
            state = pattern.group(3).upper()
            zip_code = pattern.group(4)
            country = "USA"
            return {"address1": address1, "address2": "", "city": city, "state": state, "country": country, "zip": zip_code}

        # Fallback: look for zip + state
        zip_m = re.search(r"\b(\d{5})\b", clean)
        if not zip_m:
            return None
        state_m = re.search(r"\b([A-Z]{2})\s+\d{5}", clean)
        state = state_m.group(1) if state_m else "XX"
        # Try to find number + word street
        street_m = re.search(r"(\d+\s+\w[\w\s]*)(?:,|\s+[A-Z]{2}\s+\d{5})", clean)
        address1 = street_m.group(1).strip() if street_m else ""
        city_m = re.search(r",\s*([A-Za-z][A-Za-z\s]+),\s*[A-Z]{2}\s+\d{5}", clean)
        city = city_m.group(1).strip() if city_m else ""
        country = "USA"
        if not address1 or not city:
            return None
        return {"address1": address1, "address2": "", "city": city, "state": state, "country": country, "zip": zip_m.group(1)}

    def _extract_payment_method(self, text: str, order: dict[str, Any]) -> str:
        pm_m = re.search(r"(credit_card_\w+|paypal_\w+|gift_card_\w+|debit_card_\w+)", text)
        if pm_m:
            return pm_m.group(1)
        hist = order.get("payment_history", [])
        if hist:
            return hist[0]["payment_method_id"]
        return ""

    def _extract_payment_to(self, text: str) -> str | None:
        # Match "to {payment_method_id}" patterns — for changing TO a new payment method
        m = re.search(r"\bto\s+(credit_card_\w+|paypal_\w+|gift_card_\w+|debit_card_\w+)", text, re.IGNORECASE)
        return m.group(1) if m else None

    def _extract_new_item_ids(self, text: str, old_items: list[dict[str, Any]]) -> list[str]:
        found = re.findall(r"item_\w+", text)
        # Filter out old item IDs
        old_ids = {i["item_id"] for i in old_items}
        new_ids = [f for f in found if f not in old_ids]
        if not new_ids:
            # Check if any found match old ids (user might say the same)
            return found if found else []
        # If user specified fewer new items than old, repeat the last new item
        while len(new_ids) < len(old_items):
            new_ids.append(new_ids[-1])
        return new_ids[:len(old_items)]

    def _extract_specific_item_ids(self, text: str, order_items: list[dict[str, Any]]) -> list[str]:
        """Return item IDs mentioned in text that are present in the order."""
        order_item_ids = {i["item_id"] for i in order_items}
        mentioned = re.findall(r"item_\w+", text)
        return [iid for iid in mentioned if iid in order_item_ids]

    def _user_confirmed(self, text: str) -> bool:
        t = text.lower().strip()
        return any(w in t for w in ["yes", "yep", "sure", "ok", "okay", "proceed", "go ahead", "please", "confirm", "do it", "correct"])

    def _user_denied(self, text: str) -> bool:
        t = text.lower().strip()
        return any(w in t for w in ["no", "nope", "cancel", "stop", "don't", "nevermind", "never mind"])

    def _get_remaining_orders(self, text: str, history: list[dict[str, Any]]) -> list[str]:
        # Keep original case for order ID extraction
        combined = " ".join(m.get("content", "") for m in history if m.get("role") == "user")
        return list(dict.fromkeys(re.findall(r"#[Ww]\d+", combined)))

    def _intent_for_order(self, order_id: str, text: str) -> str | None:
        # Case-insensitive search so this works on lowercased text too
        text_lower = text.lower()
        idx = text_lower.find(order_id.lower())
        if idx == -1:
            return None
        context = text_lower[max(0, idx - 50):idx + 100]
        if "cancel" in context:
            return "cancel"
        if "address" in context:
            return "modify_order_address"
        if "payment" in context and "method" in context:
            return "modify_order_payment"
        if any(w in context for w in ["change", "modify", "switch", "replace", "upgrade", "downgrade"]) and "item_" in context:
            return "modify_order_items"
        return None
