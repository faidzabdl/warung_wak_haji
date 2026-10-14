"""
Integration test — full order lifecycle.

This test exercises the complete buyer-to-seller flow using mocked service
functions (no real Supabase connection needed).  Each step verifies:
  - Correct HTTP status code
  - Required fields present in the response body

Steps (QRIS flow):
  1.  POST /orders                             → 201, has order_number + tracking_token
  2.  GET  /orders/track/{token}               → 200, has items and order_status
  3.  GET  /seller/orders                      → 200, list not empty
  4.  GET  /seller/orders/{order_number}       → 200, has items (new field names)
  5.  POST /seller/orders/{num}/verify-payment → 200, order_status=processing
  6.  POST /seller/orders/{num}/mark-ready     → 200, order_status=ready
  7.  POST /seller/orders/{num}/complete       → 200, order_status=completed
  8.  GET  /seller/history                     → 200, has pagination + summary fields

Note: Proof upload endpoint has been removed. QRIS verification goes directly
through seller's verify-payment action.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_seller_jwt, TEST_SELLER_UID

# ---------------------------------------------------------------------------
# Shared mock payloads
# ---------------------------------------------------------------------------

_ORDER_NUMBER = "ORD-20240101-LIFE"
_TRACKING_TOKEN = "plaintoken-lifecycle-abc123"
_ORDER_ID = "cccccccc-0000-0000-0000-000000000001"

_BASE_ORDER = {
    "id": _ORDER_ID,
    "order_number": _ORDER_NUMBER,
    "buyer_name": "Andi",
    "table_number": "7",
    "payment_method": "qris",
    "notes": "Extra spicy",
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "30000",
    "tracking_token_hash": "somehashvalue",
    "idempotency_key": None,
    "cancel_reason": None,
    "created_at": "2024-01-15T08:00:00",
    "updated_at": "2024-01-15T08:00:00",
}

# Items use new schema: menu_type / name / qty / subtotal / menu_id
_ITEM_SNAPSHOT = {
    "menu_name_snapshot": "Nasi Goreng",
    "menu_price_snapshot": "15000",
    "quantity": 2,
    "subtotal": "30000",
    "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
}

_ORDER_WITH_ITEMS = {
    **_BASE_ORDER,
    "items": [_ITEM_SNAPSHOT],
}

_ACTIVE_LIST = [
    {
        "order_number": _ORDER_NUMBER,
        "buyer_name": "Andi",
        "table_number": "7",
        "payment_method": "qris",
        "order_status": "awaiting_payment",
        "payment_status": "pending_payment",
        "total_amount": "30000",
        "item_count": 1,
        "created_at": "2024-01-15T08:00:00",
    }
]

_DETAIL_ITEM = {
    "menu_type": "Makanan",
    "name": "Nasi Goreng",
    "qty": 2,
    "subtotal": "30000",
    "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
}

_DETAIL_RESPONSE = {
    "order_number": _ORDER_NUMBER,
    "buyer_name": "Andi",
    "table_number": "7",
    "payment_method": "qris",
    "notes": "Extra spicy",
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "30000",
    "items": [_DETAIL_ITEM],
    "cancel_reason": None,
    "created_at": "2024-01-15T08:00:00",
    "updated_at": "2024-01-15T08:00:00",
}

# verify-payment: awaiting_payment → processing + payment_status → paid
_ORDER_AFTER_VERIFY = {
    "order_number": _ORDER_NUMBER,
    "order_status": "processing",
    "payment_status": "paid",
}

# mark-ready: processing → ready
_ORDER_AFTER_READY = {
    "order_number": _ORDER_NUMBER,
    "order_status": "ready",
}

# complete: ready → completed
_ORDER_AFTER_COMPLETE = {
    "order_number": _ORDER_NUMBER,
    "order_status": "completed",
    "payment_status": "paid",
}

_HISTORY_PAGE = {
    "data": [
        {
            "order_number": _ORDER_NUMBER,
            "buyer_name": "Andi",
            "table_number": "7",
            "payment_method": "qris",
            "order_status": "completed",
            "payment_status": "paid",
            "total_amount": "30000",
            "items": [_DETAIL_ITEM],
            "cancel_reason": None,
            "created_at": "2024-01-15T08:00:00",
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_revenue": "30000",
    "completed_count": 1,
    "cancelled_count": 0,
}


def _seller_headers() -> dict:
    return {"Authorization": f"Bearer {make_seller_jwt()}"}


# ---------------------------------------------------------------------------
# The integration test
# ---------------------------------------------------------------------------


async def test_full_order_lifecycle(client: AsyncClient):
    """
    Integration test: buyer creates QRIS order → seller verifies → marks ready
    → completes → order appears in history.

    All service calls are mocked but the test verifies the full endpoint chain
    returns correct HTTP statuses and response shapes.

    Note: Proof upload step removed — no longer part of the flow.
    """

    # ------------------------------------------------------------------
    # Step 1 — POST /orders  →  201, has order_number and tracking_token
    # ------------------------------------------------------------------
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=(_BASE_ORDER, _TRACKING_TOKEN, False)),
    ):
        step1 = await client.post(
            "/orders",
            json={
                "buyer_name": "Andi",
                "table_number": "7",
                "payment_method": "qris",
                "items": [
                    {
                        "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
                        "quantity": 2,
                    }
                ],
                "notes": "Extra spicy",
            },
        )

    assert step1.status_code == 201, f"Step 1 failed: {step1.text}"
    step1_data = step1.json()
    assert "order_number" in step1_data, "Step 1: missing order_number"
    assert "tracking_token" in step1_data, "Step 1: missing tracking_token"
    order_number = step1_data["order_number"]
    tracking_token = step1_data["tracking_token"]
    assert order_number == _ORDER_NUMBER
    assert tracking_token == _TRACKING_TOKEN

    # ------------------------------------------------------------------
    # Step 2 — GET /orders/track/{token}  →  200, has items and status
    # ------------------------------------------------------------------
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(return_value=_ORDER_WITH_ITEMS),
    ):
        step2 = await client.get(f"/orders/track/{tracking_token}")

    assert step2.status_code == 200, f"Step 2 failed: {step2.text}"
    step2_data = step2.json()
    assert "items" in step2_data, "Step 2: missing items"
    assert isinstance(step2_data["items"], list)
    assert len(step2_data["items"]) == 1
    assert "order_status" in step2_data, "Step 2: missing order_status"
    assert step2_data["order_status"] == "awaiting_payment"

    # ------------------------------------------------------------------
    # Step 3 — GET /seller/orders  →  200, list not empty
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.list_active_orders",
        new=AsyncMock(return_value=_ACTIVE_LIST),
    ):
        step3 = await client.get("/seller/orders", headers=_seller_headers())

    assert step3.status_code == 200, f"Step 3 failed: {step3.text}"
    step3_data = step3.json()
    assert isinstance(step3_data, list), "Step 3: expected list"
    assert len(step3_data) >= 1, "Step 3: expected at least one active order"
    assert step3_data[0]["payment_method"] == "qris", "Step 3: missing payment_method"

    # ------------------------------------------------------------------
    # Step 4 — GET /seller/orders/{order_number}  →  200, has items (new fields)
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.get_order_detail",
        new=AsyncMock(return_value=_DETAIL_RESPONSE),
    ):
        step4 = await client.get(
            f"/seller/orders/{order_number}", headers=_seller_headers()
        )

    assert step4.status_code == 200, f"Step 4 failed: {step4.text}"
    step4_data = step4.json()
    assert "items" in step4_data, "Step 4: missing items"
    assert isinstance(step4_data["items"], list)
    item = step4_data["items"][0]
    assert "name" in item, "Step 4: item missing 'name'"
    assert "qty" in item, "Step 4: item missing 'qty'"
    assert "menu_type" in item, "Step 4: item missing 'menu_type'"
    assert "payment_proof_url" not in step4_data, "Step 4: payment_proof_url must not exist"

    # ------------------------------------------------------------------
    # Step 5 — POST /seller/orders/{num}/verify-payment  →  200 processing+paid
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.verify_payment",
        new=AsyncMock(return_value=_ORDER_AFTER_VERIFY),
    ):
        step5 = await client.post(
            f"/seller/orders/{order_number}/verify-payment",
            headers=_seller_headers(),
        )

    assert step5.status_code == 200, f"Step 5 failed: {step5.text}"
    assert step5.json()["order_status"] == "processing", "Step 5: wrong order_status"
    assert step5.json()["payment_status"] == "paid", "Step 5: wrong payment_status"

    # ------------------------------------------------------------------
    # Step 6 — POST /seller/orders/{num}/mark-ready  →  200, ready
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.mark_ready",
        new=AsyncMock(return_value=_ORDER_AFTER_READY),
    ):
        step6 = await client.post(
            f"/seller/orders/{order_number}/mark-ready",
            headers=_seller_headers(),
        )

    assert step6.status_code == 200, f"Step 6 failed: {step6.text}"
    assert step6.json()["order_status"] == "ready", "Step 6: wrong order_status"

    # ------------------------------------------------------------------
    # Step 7 — POST /seller/orders/{num}/complete  →  200, completed
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.complete_order",
        new=AsyncMock(return_value=_ORDER_AFTER_COMPLETE),
    ):
        step7 = await client.post(
            f"/seller/orders/{order_number}/complete",
            headers=_seller_headers(),
        )

    assert step7.status_code == 200, f"Step 7 failed: {step7.text}"
    assert step7.json()["order_status"] == "completed", "Step 7: wrong order_status"

    # ------------------------------------------------------------------
    # Step 8 — GET /seller/history  →  200, has pagination + summary fields
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.get_history",
        new=AsyncMock(return_value=_HISTORY_PAGE),
    ):
        step8 = await client.get("/seller/history", headers=_seller_headers())

    assert step8.status_code == 200, f"Step 8 failed: {step8.text}"
    step8_data = step8.json()
    for field in ("data", "total", "page", "page_size", "total_revenue", "completed_count", "cancelled_count"):
        assert field in step8_data, f"Step 8: missing field '{field}'"
    assert isinstance(step8_data["data"], list)
    assert any(
        o["order_number"] == _ORDER_NUMBER for o in step8_data["data"]
    ), "Step 8: completed order not found in history"
