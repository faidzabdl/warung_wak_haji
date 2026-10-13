"""
Tests for Seller Order Management endpoints (Sub-Task 6).

Service functions are mocked at the service layer — no real Supabase
connection is required.

Tests:
  1.  test_list_active_orders_no_auth
  2.  test_list_active_orders_wrong_uid
  3.  test_list_active_orders_success
  4.  test_get_order_detail_success
  5.  test_get_order_detail_not_found
  6.  test_verify_payment_success
  7.  test_verify_payment_wrong_state
  8.  test_reject_payment_success
  9.  test_reject_payment_missing_reason
  10. test_start_processing_success
  11. test_start_processing_wrong_state
  12. test_complete_order_success
  13. test_complete_order_wrong_state
  14. test_cancel_order_success
  15. test_cancel_order_already_completed
  16. test_cancel_order_missing_reason
  17. test_get_history_no_auth
  18. test_get_history_success
  19. test_get_history_pagination
  20. test_get_history_date_filter
  21. test_get_history_status_filter
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from tests.conftest import make_seller_jwt, make_wrong_jwt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SERVICE = "routers.seller"


def _auth() -> dict:
    return {"Authorization": f"Bearer {make_seller_jwt()}"}


def _wrong_auth() -> dict:
    return {"Authorization": f"Bearer {make_wrong_jwt()}"}


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

ORDER_LIST = [
    {
        "order_number": "ORD-20240101-AAAA",
        "buyer_name": "Budi",
        "order_status": "awaiting_payment",
        "payment_status": "pending_payment",
        "total_amount": "30000",
        "item_count": 2,
        "created_at": "2024-01-01T10:00:00",
    },
    {
        "order_number": "ORD-20240101-BBBB",
        "buyer_name": "Siti",
        "order_status": "waiting_processing",
        "payment_status": "paid",
        "total_amount": "15000",
        "item_count": 1,
        "created_at": "2024-01-01T11:00:00",
    },
]

ORDER_DETAIL = {
    "order_number": "ORD-20240101-AAAA",
    "buyer_name": "Budi",
    "notes": None,
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
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00",
}

ORDER_AFTER_VERIFY = {
    "order_number": "ORD-20240101-AAAA",
    "order_status": "waiting_processing",
    "payment_status": "paid",
}

ORDER_AFTER_REJECT = {
    "order_number": "ORD-20240101-AAAA",
    "order_status": "cancelled",
    "payment_status": "rejected",
}

ORDER_AFTER_START = {
    "order_number": "ORD-20240101-BBBB",
    "order_status": "processing",
}

ORDER_AFTER_COMPLETE = {
    "order_number": "ORD-20240101-BBBB",
    "order_status": "completed",
}

ORDER_AFTER_CANCEL = {
    "order_number": "ORD-20240101-AAAA",
    "order_status": "cancelled",
}

HISTORY_RESPONSE = {
    "data": [
        {
            "order_number": "ORD-20240101-AAAA",
            "buyer_name": "Budi",
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
            "created_at": "2024-01-01T10:00:00",
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
}


# ===========================================================================
# 1. test_list_active_orders_no_auth
# ===========================================================================


async def test_list_active_orders_no_auth(client: AsyncClient):
    """No Authorization header → 401."""
    response = await client.get("/seller/orders")
    assert response.status_code == 401


# ===========================================================================
# 2. test_list_active_orders_wrong_uid
# ===========================================================================


async def test_list_active_orders_wrong_uid(client: AsyncClient):
    """Valid JWT but wrong UID → 403."""
    response = await client.get("/seller/orders", headers=_wrong_auth())
    assert response.status_code == 403


# ===========================================================================
# 3. test_list_active_orders_success
# ===========================================================================


async def test_list_active_orders_success(client: AsyncClient):
    """Mock returns 2 active orders → 200 list of 2."""
    with patch(
        f"{_SERVICE}.list_active_orders",
        new_callable=AsyncMock,
        return_value=ORDER_LIST,
    ):
        response = await client.get("/seller/orders", headers=_auth())

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["order_number"] == "ORD-20240101-AAAA"
    assert data[1]["item_count"] == 1


# ===========================================================================
# 4. test_get_order_detail_success
# ===========================================================================


async def test_get_order_detail_success(client: AsyncClient):
    """Mock returns full order detail with items and signed URL → 200."""
    with patch(
        f"{_SERVICE}.get_order_detail",
        new_callable=AsyncMock,
        return_value=ORDER_DETAIL,
    ):
        response = await client.get(
            "/seller/orders/ORD-20240101-AAAA", headers=_auth()
        )

    assert response.status_code == 200
    data = response.json()
    assert data["order_number"] == "ORD-20240101-AAAA"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["items"][0]["menu_name"] == "Nasi Goreng"
    assert data["payment_proof_url"].startswith("https://")


# ===========================================================================
# 5. test_get_order_detail_not_found
# ===========================================================================


async def test_get_order_detail_not_found(client: AsyncClient):
    """Service raises 404 → 404 ORDER_NOT_FOUND."""
    with patch(
        f"{_SERVICE}.get_order_detail",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=404,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}},
        ),
    ):
        response = await client.get(
            "/seller/orders/ORD-NOTEXIST", headers=_auth()
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


# ===========================================================================
# 6. test_verify_payment_success
# ===========================================================================


async def test_verify_payment_success(client: AsyncClient):
    """Order in correct state → 200 with updated statuses."""
    with patch(
        f"{_SERVICE}.verify_payment",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_VERIFY,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/verify-payment", headers=_auth()
        )

    assert response.status_code == 200
    data = response.json()
    assert data["order_status"] == "waiting_processing"
    assert data["payment_status"] == "paid"


# ===========================================================================
# 7. test_verify_payment_wrong_state
# ===========================================================================


async def test_verify_payment_wrong_state(client: AsyncClient):
    """payment_status=paid → 409 INVALID_STATUS_TRANSITION."""
    with patch(
        f"{_SERVICE}.verify_payment",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Cannot verify payment: payment status is not pending_verification",
                }
            },
        ),
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/verify-payment", headers=_auth()
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ===========================================================================
# 8. test_reject_payment_success
# ===========================================================================


async def test_reject_payment_success(client: AsyncClient):
    """Order pending_verification → 200 with cancelled order."""
    with patch(
        f"{_SERVICE}.reject_payment",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_REJECT,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/reject-payment",
            json={"reason": "Bukti pembayaran tidak valid"},
            headers=_auth(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["order_status"] == "cancelled"
    assert data["payment_status"] == "rejected"


# ===========================================================================
# 9. test_reject_payment_missing_reason
# ===========================================================================


async def test_reject_payment_missing_reason(client: AsyncClient):
    """Empty reason string → 422 validation error."""
    response = await client.post(
        "/seller/orders/ORD-20240101-AAAA/reject-payment",
        json={"reason": ""},
        headers=_auth(),
    )
    assert response.status_code == 422


# ===========================================================================
# 10. test_start_processing_success
# ===========================================================================


async def test_start_processing_success(client: AsyncClient):
    """Order waiting_processing → 200 with processing status."""
    with patch(
        f"{_SERVICE}.start_processing",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_START,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/start-processing", headers=_auth()
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "processing"


# ===========================================================================
# 11. test_start_processing_wrong_state
# ===========================================================================


async def test_start_processing_wrong_state(client: AsyncClient):
    """Order still awaiting_payment → 409 INVALID_STATUS_TRANSITION."""
    with patch(
        f"{_SERVICE}.start_processing",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Cannot start processing: order status is not waiting_processing",
                }
            },
        ),
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/start-processing", headers=_auth()
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ===========================================================================
# 12. test_complete_order_success
# ===========================================================================


async def test_complete_order_success(client: AsyncClient):
    """Order processing → 200 with completed status."""
    with patch(
        f"{_SERVICE}.complete_order",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_COMPLETE,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/complete", headers=_auth()
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "completed"


# ===========================================================================
# 13. test_complete_order_wrong_state
# ===========================================================================


async def test_complete_order_wrong_state(client: AsyncClient):
    """Order waiting_processing (not processing) → 409."""
    with patch(
        f"{_SERVICE}.complete_order",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Cannot complete order: order status is not processing",
                }
            },
        ),
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/complete", headers=_auth()
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ===========================================================================
# 14. test_cancel_order_success
# ===========================================================================


async def test_cancel_order_success(client: AsyncClient):
    """Order awaiting_payment → 200 with cancelled status."""
    with patch(
        f"{_SERVICE}.cancel_order",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_CANCEL,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/cancel",
            json={"reason": "Stok habis"},
            headers=_auth(),
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "cancelled"


# ===========================================================================
# 15. test_cancel_order_already_completed
# ===========================================================================


async def test_cancel_order_already_completed(client: AsyncClient):
    """Order already completed → 409."""
    with patch(
        f"{_SERVICE}.cancel_order",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Pesanan sudah selesai atau dibatalkan",
                }
            },
        ),
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/cancel",
            json={"reason": "Terlambat"},
            headers=_auth(),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ===========================================================================
# 16. test_cancel_order_missing_reason
# ===========================================================================


async def test_cancel_order_missing_reason(client: AsyncClient):
    """Empty reason → 422 validation error."""
    response = await client.post(
        "/seller/orders/ORD-20240101-AAAA/cancel",
        json={"reason": ""},
        headers=_auth(),
    )
    assert response.status_code == 422


# ===========================================================================
# 17. test_get_history_no_auth
# ===========================================================================


async def test_get_history_no_auth(client: AsyncClient):
    """No Authorization header → 401."""
    response = await client.get("/seller/history")
    assert response.status_code == 401


# ===========================================================================
# 18. test_get_history_success
# ===========================================================================


async def test_get_history_success(client: AsyncClient):
    """Mock returns paginated list → 200 with data/total/page/page_size."""
    with patch(
        f"{_SERVICE}.get_history",
        new_callable=AsyncMock,
        return_value=HISTORY_RESPONSE,
    ):
        response = await client.get("/seller/history", headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert isinstance(body["data"], list)
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20


# ===========================================================================
# 19. test_get_history_pagination
# ===========================================================================


async def test_get_history_pagination(client: AsyncClient):
    """page=2, page_size=5 → service called with those exact values."""
    mock_service = AsyncMock(
        return_value={
            "data": [],
            "total": 10,
            "page": 2,
            "page_size": 5,
        }
    )
    with patch(f"{_SERVICE}.get_history", mock_service):
        response = await client.get(
            "/seller/history?page=2&page_size=5", headers=_auth()
        )

    assert response.status_code == 200
    mock_service.assert_called_once_with(
        page=2,
        page_size=5,
        status=None,
        date_from=None,
        date_to=None,
    )


# ===========================================================================
# 20. test_get_history_date_filter
# ===========================================================================


async def test_get_history_date_filter(client: AsyncClient):
    """date_from and date_to are forwarded correctly to the service."""
    mock_service = AsyncMock(
        return_value={"data": [], "total": 0, "page": 1, "page_size": 20}
    )
    with patch(f"{_SERVICE}.get_history", mock_service):
        response = await client.get(
            "/seller/history?date_from=2024-01-01&date_to=2024-01-31",
            headers=_auth(),
        )

    assert response.status_code == 200
    mock_service.assert_called_once_with(
        page=1,
        page_size=20,
        status=None,
        date_from="2024-01-01",
        date_to="2024-01-31",
    )


# ===========================================================================
# 21. test_get_history_status_filter
# ===========================================================================


async def test_get_history_status_filter(client: AsyncClient):
    """status=completed filter is forwarded correctly to the service."""
    mock_service = AsyncMock(
        return_value={"data": [], "total": 0, "page": 1, "page_size": 20}
    )
    with patch(f"{_SERVICE}.get_history", mock_service):
        response = await client.get(
            "/seller/history?status=completed", headers=_auth()
        )

    assert response.status_code == 200
    mock_service.assert_called_once_with(
        page=1,
        page_size=20,
        status="completed",
        date_from=None,
        date_to=None,
    )
