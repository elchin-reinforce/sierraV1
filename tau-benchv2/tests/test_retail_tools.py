"""Tests for retail domain tools."""
from __future__ import annotations
import copy
import pytest
import taufreebench.domains.retail.tools  # noqa: F401 — registers tools
from taufreebench.core.tool import get_domain_tools


@pytest.fixture
def tools():
    return get_domain_tools("retail")


def test_find_user_by_email(db, tools):
    result = tools["find_user_id_by_email"](db, email="mei.patel@example.com")
    assert result == "mei_patel_7272"


def test_find_user_by_email_not_found(db, tools):
    result = tools["find_user_id_by_email"](db, email="nobody@example.com")
    assert result.startswith("Error:")


def test_find_user_by_name_zip(db, tools):
    result = tools["find_user_id_by_name_zip"](db, first_name="Mei", last_name="Patel", zip="94102")
    assert result == "mei_patel_7272"


def test_get_order_details(db, tools):
    order = tools["get_order_details"](db, order_id="#W4082615")
    assert order["user_id"] == "mei_patel_7272"
    assert order["status"] == "pending"


def test_get_order_not_found(db, tools):
    result = tools["get_order_details"](db, order_id="#WXXXXXX")
    assert "error" in result


def test_cancel_pending_order(db, tools):
    result = tools["cancel_pending_order"](db, order_id="#W4082615", reason="ordered by mistake")
    assert result["status"] == "cancelled"
    assert db["orders"]["#W4082615"]["status"] == "cancelled"
    assert db["orders"]["#W4082615"]["cancellation_reason"] == "ordered by mistake"


def test_cannot_cancel_delivered_order(db, tools):
    result = tools["cancel_pending_order"](db, order_id="#W7382910", reason="no longer needed")
    assert "Error:" in str(result.get("error", ""))
    assert db["orders"]["#W7382910"]["status"] == "delivered"


def test_cannot_cancel_processed_order(db, tools):
    result = tools["cancel_pending_order"](db, order_id="#W2948301", reason="no longer needed")
    assert "Error:" in str(result.get("error", ""))


def test_cancel_invalid_reason(db, tools):
    result = tools["cancel_pending_order"](db, order_id="#W4082615", reason="I changed my mind")
    assert "Error:" in str(result.get("error", ""))


def test_return_delivered_items(db, tools):
    result = tools["return_delivered_order_items"](db, order_id="#W7382910", item_ids=["item_jeans_30_dark"], payment_method_id="credit_card_5421098")
    assert result["status"] == "return requested"
    assert db["orders"]["#W7382910"]["status"] == "return requested"
    assert result["refund_amount"] == 49.99


def test_cannot_return_pending_order(db, tools):
    result = tools["return_delivered_order_items"](db, order_id="#W4082615", item_ids=["item_tshirt_m_blue"], payment_method_id="credit_card_9513926")
    assert "Error:" in str(result.get("error", ""))


def test_exchange_delivered_items(db, tools):
    result = tools["exchange_delivered_order_items"](
        db,
        order_id="#W1937482",
        item_ids=["item_tshirt_s_red"],
        new_item_ids=["item_tshirt_m_blue"],
        payment_method_id="credit_card_3847291",
    )
    assert result["status"] == "exchange requested"
    assert db["orders"]["#W1937482"]["status"] == "exchange requested"


def test_cannot_exchange_processed_order(db, tools):
    result = tools["exchange_delivered_order_items"](
        db,
        order_id="#W2948301",
        item_ids=["item_speaker_black_standard"],
        new_item_ids=["item_speaker_red_standard"],
        payment_method_id="credit_card_7384920",
    )
    assert "Error:" in str(result.get("error", ""))


def test_modify_pending_items_same_product_only(db, tools):
    # Trying to swap t-shirt for jeans (different product) should fail
    result = tools["modify_pending_order_items"](
        db,
        order_id="#W4082615",
        item_ids=["item_tshirt_m_blue"],
        new_item_ids=["item_jeans_30_dark"],
        payment_method_id="credit_card_9513926",
    )
    assert "Error:" in str(result.get("error", ""))
    assert db["orders"]["#W4082615"]["items"][0]["item_id"] == "item_tshirt_m_blue"


def test_modify_pending_items_success(db, tools):
    result = tools["modify_pending_order_items"](
        db,
        order_id="#W6172839",
        item_ids=["item_headphones_black_pro"],
        new_item_ids=["item_headphones_black_standard"],
        payment_method_id="credit_card_1029384",
    )
    assert "error" not in result
    assert db["orders"]["#W6172839"]["items"][0]["item_id"] == "item_headphones_black_standard"
    # Pro is $149.99, Standard is $79.99 → refund $70
    assert result["price_difference"] == pytest.approx(-70.0)


def test_payment_method_must_belong_to_user(db, tools):
    # Try to return with a payment method that belongs to a different user
    result = tools["return_delivered_order_items"](
        db,
        order_id="#W7382910",
        item_ids=["item_jeans_30_dark"],
        payment_method_id="credit_card_9513926",  # Mei's card, not Yusuf's
    )
    assert "Error:" in str(result.get("error", ""))


def test_modify_order_address(db, tools):
    result = tools["modify_pending_order_address"](
        db,
        order_id="#W5849302",
        address1="789 Pine Ave",
        address2="",
        city="Austin",
        state="TX",
        country="USA",
        zip="78702",
    )
    assert "error" not in result
    assert db["orders"]["#W5849302"]["shipping_address"]["zip"] == "78702"


def test_modify_user_address(db, tools):
    result = tools["modify_user_address"](
        db,
        user_id="aisha_williams_2234",
        address1="456 Maple St",
        address2="",
        city="Seattle",
        state="WA",
        country="USA",
        zip="98102",
    )
    assert "error" not in result
    assert db["users"]["aisha_williams_2234"]["address"]["zip"] == "98102"


def test_calculate(db, tools):
    result = tools["calculate"](db, expression="149.99 - 79.99")
    assert result == "70.0"


def test_list_product_types(db, tools):
    result = tools["list_all_product_types"](db)
    assert "prod_tshirt_001" in result
    assert len(result) >= 12
