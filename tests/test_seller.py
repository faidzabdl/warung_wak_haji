"""
Tests for Seller Order Management endpoints.

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
  9.  test_reject_payment_no_reason (reason is optional → still 200)
  10. test_start_processing_success
  11. test_start_processing_wrong_state
  12. test_mark_ready_success
  13. test_complete_order_success
  14. test_complete_order_wrong_state
  15. test_cancel_order_success
  16. test_cancel_order_already_completed
  17. test_cancel_order_no_reason (reason is optional → still 200)
  18. test_get_history_no_auth
  19. test_get_history_success
  20. test_get_history_pagination
  21. test_get_history_date_filter
  22. test_get_history_status_filter
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

# Items use the NEW schema: menu_type / name / qty / subtotal / menu_id
_ITEM_1 = {
    "menu_type": "Makanan",
    "name": "Nasi Goreng",
    "qty": 2,
    "subtotal": "30000",
    "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
}

ORDER_LIST = [
    {
        "order_number": "ORD-20240101-AAAA",
        "buyer_name": "Budi",
        "table_number": "5",
        "payment_method": "qris",
        "order_status": "awaiting_payment",
        "payment_status": "pending_payment",
        "total_amount": "30000",
        "item_count": 2,
        "created_at": "2024-01-01T10:00:00",
    },
    {
        "order_number": "ORD-20240101-BBBB",
        "buyer_name": "Siti",
        "table_number": "3",
        "payment_method": "cash",
        "order_status": "waiting_processing",
        "payment_status": "pending_payment",
        "total_amount": "15000",
        "item_count": 1,
        "created_at": "2024-01-01T11:00:00",
    },
]

ORDER_DETAIL = {
    "order_number": "ORD-20240101-AAAA",
    "buyer_name": "Budi",
    "table_number": "5",
    "payment_method": "qris",
    "notes": None,
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "30000",
    "items": [_ITEM_1],
    "cancel_reason": None,
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00",
}

# verify-payment: awaiting_payment → processing, payment_status → paid
ORDER_AFTER_VERIFY = {
    "order_number": "ORD-20240101-AAAA",
    "order_status": "processing",
    "payment_status": "paid",
}

ORDER_AFTER_REJECT = {
    "order_number": "ORD-20240101-AAAA",
    "order_status": "cancelled",
    "payment_status": "rejected",
}

# start-processing: waiting_processing → processing
ORDER_AFTER_START = {
    "order_number": "ORD-20240101-BBBB",
    "order_status": "processing",
}

# mark-ready: processing → ready
ORDER_AFTER_READY = {
    "order_number": "ORD-20240101-BBBB",
    "order_status": "ready",
}

# complete: ready → completed
ORDER_AFTER_COMPLETE = {
    "order_number": "ORD-20240101-BBBB",
    "order_status": "completed",
    "payment_status": "paid",
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
            "table_number": "5",
            "payment_method": "qris",
            "order_status": "completed",
            "payment_status": "paid",
            "total_amount": "30000",
            "items": [_ITEM_1],
            "cancel_reason": None,
            "created_at": "2024-01-01T10:00:00",
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_revenue": "30000",
    "completed_count": 1,
    "cancelled_count": 0,
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
    """Mock returns 2 active orders → 200 list of 2 with new fields."""
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
    assert data[0]["table_number"] == "5"
    assert data[0]["payment_method"] == "qris"
    assert data[1]["item_count"] == 1
    assert data[1]["payment_method"] == "cash"


# ===========================================================================
# 4. test_get_order_detail_success
# ===========================================================================


async def test_get_order_detail_success(client: AsyncClient):
    """Mock returns full order detail with items → 200. No payment_proof_url."""
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
    assert data["table_number"] == "5"
    assert data["payment_method"] == "qris"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Nasi Goreng"
    assert data["items"][0]["qty"] == 2
    assert data["items"][0]["menu_type"] == "Makanan"
    # payment_proof_url must NOT exist in new schema
    assert "payment_proof_url" not in data
    assert "reject_reason" not in data


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
    """QRIS order in awaiting_payment → 200: processing + paid."""
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
    assert data["order_status"] == "processing"
    assert data["payment_status"] == "paid"


# ===========================================================================
# 7. test_verify_payment_wrong_state
# ===========================================================================


async def test_verify_payment_wrong_state(client: AsyncClient):
    """Order not awaiting_payment → 409 INVALID_STATUS_TRANSITION."""
    with patch(
        f"{_SERVICE}.verify_payment",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Cannot verify payment: order status is not awaiting_payment",
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
    """QRIS order awaiting_payment + reason provided → 200 cancelled + rejected."""
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
# 9. test_reject_payment_no_reason (reason is optional)
# ===========================================================================


async def test_reject_payment_no_reason(client: AsyncClient):
    """reason is optional → null reason still accepted → 200."""
    with patch(
        f"{_SERVICE}.reject_payment",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_REJECT,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/reject-payment",
            json={},  # no reason field
            headers=_auth(),
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "cancelled"


# ===========================================================================
# 10. test_start_processing_success
# ===========================================================================


async def test_start_processing_success(client: AsyncClient):
    """Cash order waiting_processing → 200 with processing status."""
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
    """Order not in waiting_processing → 409 INVALID_STATUS_TRANSITION."""
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
# 12. test_mark_ready_success
# ===========================================================================


async def test_mark_ready_success(client: AsyncClient):
    """Order processing → 200 with ready status."""
    with patch(
        f"{_SERVICE}.mark_ready",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_READY,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/mark-ready", headers=_auth()
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "ready"


# ===========================================================================
# 13. test_complete_order_success
# ===========================================================================


async def test_complete_order_success(client: AsyncClient):
    """Order ready → 200 with completed status + payment_status."""
    with patch(
        f"{_SERVICE}.complete_order",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_COMPLETE,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-BBBB/complete", headers=_auth()
        )

    assert response.status_code == 200
    data = response.json()
    assert data["order_status"] == "completed"
    assert data["payment_status"] == "paid"


# ===========================================================================
# 14. test_complete_order_wrong_state
# ===========================================================================


async def test_complete_order_wrong_state(client: AsyncClient):
    """Order not in ready state → 409 INVALID_STATUS_TRANSITION."""
    with patch(
        f"{_SERVICE}.complete_order",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": "Cannot complete order: order status is not ready",
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
# 15. test_cancel_order_success
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
# 16. test_cancel_order_already_completed
# ===========================================================================


async def test_cancel_order_already_completed(client: AsyncClient):
    """Order already completed (not awaiting_payment/waiting_processing) → 409."""
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
# 17. test_cancel_order_no_reason (reason is optional)
# ===========================================================================


async def test_cancel_order_no_reason(client: AsyncClient):
    """reason is optional → null reason still accepted → 200."""
    with patch(
        f"{_SERVICE}.cancel_order",
        new_callable=AsyncMock,
        return_value=ORDER_AFTER_CANCEL,
    ):
        response = await client.post(
            "/seller/orders/ORD-20240101-AAAA/cancel",
            json={},  # no reason field
            headers=_auth(),
        )

    assert response.status_code == 200
    assert response.json()["order_status"] == "cancelled"


# ===========================================================================
# 18. test_get_history_no_auth
# ===========================================================================


async def test_get_history_no_auth(client: AsyncClient):
    """No Authorization header → 401."""
    response = await client.get("/seller/history")
    assert response.status_code == 401


# ===========================================================================
# 19. test_get_history_success
# ===========================================================================


async def test_get_history_success(client: AsyncClient):
    """Mock returns paginated list with summary stats → 200."""
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
    assert "total_revenue" in body
    assert "completed_count" in body
    assert "cancelled_count" in body
    assert isinstance(body["data"], list)
    assert body["total"] == 1
    assert body["completed_count"] == 1
    assert body["cancelled_count"] == 0
    # items use new field names
    item = body["data"][0]["items"][0]
    assert item["name"] == "Nasi Goreng"
    assert item["qty"] == 2
    assert item["menu_type"] == "Makanan"


# ===========================================================================
# 20. test_get_history_pagination
# ===========================================================================


async def test_get_history_pagination(client: AsyncClient):
    """page=2, page_size=5 → service called with those exact values."""
    mock_service = AsyncMock(
        return_value={
            "data": [],
            "total": 10,
            "page": 2,
            "page_size": 5,
            "total_revenue": "0",
            "completed_count": 0,
            "cancelled_count": 0,
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
# 21. test_get_history_date_filter
# ===========================================================================


async def test_get_history_date_filter(client: AsyncClient):
    """date_from and date_to are forwarded correctly to the service."""
    mock_service = AsyncMock(
        return_value={
            "data": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_revenue": "0",
            "completed_count": 0,
            "cancelled_count": 0,
        }
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
# 22. test_get_history_status_filter
# ===========================================================================


async def test_get_history_status_filter(client: AsyncClient):
    """status=completed filter is forwarded correctly to the service."""
    mock_service = AsyncMock(
        return_value={
            "data": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_revenue": "0",
            "completed_count": 0,
            "cancelled_count": 0,
        }
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
