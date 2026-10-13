"""
Integration test — full order lifecycle.

This test exercises the complete buyer-to-seller flow using mocked service
functions (no real Supabase connection needed).  Each step verifies:
  - Correct HTTP status code
  - Required fields present in the response body

Steps:
  1.  POST /orders                             → 201, has order_number + tracking_token
  2.  GET  /orders/track/{token}               → 200, has items and order_status
  3.  POST /orders/{order_number}/proof        → 200, payment_status=pending_verification
  4.  GET  /seller/orders                      → 200, list not empty
  5.  GET  /seller/orders/{order_number}       → 200, has items
  6.  POST /seller/orders/{num}/verify-payment → 200
  7.  POST /seller/orders/{num}/start-processing → 200
  8.  POST /seller/orders/{num}/complete       → 200
  9.  GET  /seller/history                     → 200, has pagination fields
"""
from io import BytesIO
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
    "notes": "Extra spicy",
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "30000",
    "tracking_token_hash": "somehashvalue",
    "idempotency_key": None,
    "payment_proof_path": None,
    "cancel_reason": None,
    "reject_reason": None,
    "created_at": "2024-01-15T08:00:00",
    "updated_at": "2024-01-15T08:00:00",
}

_ORDER_WITH_ITEMS = {
    **_BASE_ORDER,
    "items": [
        {
            # Router reads these DB column names from the service result
            "menu_name_snapshot": "Nasi Goreng",
            "menu_price_snapshot": "15000",
            "quantity": 2,
            "subtotal": "30000",
            "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
        }
    ],
}

_ORDER_AFTER_PROOF = {
    **_BASE_ORDER,
    "payment_status": "pending_verification",
    "payment_proof_path": f"payment-proofs/{_ORDER_ID}/proof.jpg",
}

_ACTIVE_LIST = [
    {
        "order_number": _ORDER_NUMBER,
        "buyer_name": "Andi",
        "order_status": "awaiting_payment",
        "payment_status": "pending_verification",
        "total_amount": "30000",
        "item_count": 1,
        "created_at": "2024-01-15T08:00:00",
    }
]

_DETAIL_RESPONSE = {
    "order_number": _ORDER_NUMBER,
    "buyer_name": "Andi",
    "notes": "Extra spicy",
    "order_status": "awaiting_payment",
    "payment_status": "pending_verification",
    "total_amount": "30000",
    "items": [
        {
            "menu_name": "Nasi Goreng",
            "menu_price": "15000",
            "quantity": 2,
            "subtotal": "30000",
            "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
        }
    ],
    "payment_proof_url": "https://supabase.example.com/signed/proof.jpg",
    "cancel_reason": None,
    "reject_reason": None,
    "created_at": "2024-01-15T08:00:00",
    "updated_at": "2024-01-15T08:00:00",
}

_ORDER_AFTER_VERIFY = {
    **_BASE_ORDER,
    "order_status": "waiting_processing",
    "payment_status": "paid",
}

_ORDER_AFTER_START = {
    **_ORDER_AFTER_VERIFY,
    "order_status": "processing",
}

_ORDER_AFTER_COMPLETE = {
    **_ORDER_AFTER_START,
    "order_status": "completed",
}

_HISTORY_PAGE = {
    "data": [
        {
            "order_number": _ORDER_NUMBER,
            "buyer_name": "Andi",
            "order_status": "completed",
            "payment_status": "paid",
            "total_amount": "30000",
            "items": [
                {
                    "menu_name": "Nasi Goreng",
                    "menu_price": "15000",
                    "quantity": 2,
                    "subtotal": "30000",
                    "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
                }
            ],
            "cancel_reason": None,
            "reject_reason": None,
            "created_at": "2024-01-15T08:00:00",
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
}

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100


def _seller_headers() -> dict:
    return {"Authorization": f"Bearer {make_seller_jwt()}"}


# ---------------------------------------------------------------------------
# The integration test
# ---------------------------------------------------------------------------


async def test_full_order_lifecycle(client: AsyncClient):
    """
    Integration test: buyer creates order → uploads proof → seller verifies
    → seller starts processing → seller completes → order appears in history.

    All service calls are mocked but the test verifies the full endpoint chain
    returns correct HTTP statuses and response shapes.
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

    # ------------------------------------------------------------------
    # Step 3 — POST /orders/{order_number}/proof  →  200, pending_verification
    # ------------------------------------------------------------------
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(return_value=_ORDER_AFTER_PROOF),
    ):
        step3 = await client.post(
            f"/orders/{order_number}/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": tracking_token},
        )

    assert step3.status_code == 200, f"Step 3 failed: {step3.text}"
    step3_data = step3.json()
    assert step3_data["payment_status"] == "pending_verification", (
        f"Step 3: expected payment_status=pending_verification, got {step3_data.get('payment_status')}"
    )

    # ------------------------------------------------------------------
    # Step 4 — GET /seller/orders  →  200, list not empty
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.list_active_orders",
        new=AsyncMock(return_value=_ACTIVE_LIST),
    ):
        step4 = await client.get("/seller/orders", headers=_seller_headers())

    assert step4.status_code == 200, f"Step 4 failed: {step4.text}"
    step4_data = step4.json()
    assert isinstance(step4_data, list), "Step 4: expected list"
    assert len(step4_data) >= 1, "Step 4: expected at least one active order"

    # ------------------------------------------------------------------
    # Step 5 — GET /seller/orders/{order_number}  →  200, has items
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.get_order_detail",
        new=AsyncMock(return_value=_DETAIL_RESPONSE),
    ):
        step5 = await client.get(
            f"/seller/orders/{order_number}", headers=_seller_headers()
        )

    assert step5.status_code == 200, f"Step 5 failed: {step5.text}"
    step5_data = step5.json()
    assert "items" in step5_data, "Step 5: missing items"
    assert isinstance(step5_data["items"], list)

    # ------------------------------------------------------------------
    # Step 6 — POST /seller/orders/{order_number}/verify-payment  →  200
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.verify_payment",
        new=AsyncMock(return_value=_ORDER_AFTER_VERIFY),
    ):
        step6 = await client.post(
            f"/seller/orders/{order_number}/verify-payment",
            headers=_seller_headers(),
        )

    assert step6.status_code == 200, f"Step 6 failed: {step6.text}"

    # ------------------------------------------------------------------
    # Step 7 — POST /seller/orders/{order_number}/start-processing  →  200
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.start_processing",
        new=AsyncMock(return_value=_ORDER_AFTER_START),
    ):
        step7 = await client.post(
            f"/seller/orders/{order_number}/start-processing",
            headers=_seller_headers(),
        )

    assert step7.status_code == 200, f"Step 7 failed: {step7.text}"

    # ------------------------------------------------------------------
    # Step 8 — POST /seller/orders/{order_number}/complete  →  200
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.complete_order",
        new=AsyncMock(return_value=_ORDER_AFTER_COMPLETE),
    ):
        step8 = await client.post(
            f"/seller/orders/{order_number}/complete",
            headers=_seller_headers(),
        )

    assert step8.status_code == 200, f"Step 8 failed: {step8.text}"

    # ------------------------------------------------------------------
    # Step 9 — GET /seller/history  →  200, has pagination fields
    # ------------------------------------------------------------------
    with patch(
        "routers.seller.get_history",
        new=AsyncMock(return_value=_HISTORY_PAGE),
    ):
        step9 = await client.get("/seller/history", headers=_seller_headers())

    assert step9.status_code == 200, f"Step 9 failed: {step9.text}"
    step9_data = step9.json()
    for field in ("data", "total", "page", "page_size"):
        assert field in step9_data, f"Step 9: missing pagination field '{field}'"
    assert isinstance(step9_data["data"], list)
    # Confirm the completed order is present in history
    assert any(
        o["order_number"] == _ORDER_NUMBER for o in step9_data["data"]
    ), "Step 9: completed order not found in history"
