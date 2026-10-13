"""
Tests for Order API endpoints (Sub-Task 5).

All service-layer functions are mocked so no real Supabase connection is needed.
"""
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ORDER = {
    "id": "bbbbbbbb-0000-0000-0000-000000000001",
    "order_number": "ORD-20240101-ABCD",
    "buyer_name": "Budi",
    "notes": None,
    "total_amount": "30000",
    "payment_status": "pending_payment",
    "order_status": "awaiting_payment",
    "tracking_token_hash": "fakehash",
    "payment_proof_path": None,
    "idempotency_key": None,
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00",
}

SAMPLE_ORDER_WITH_ITEMS = {
    **SAMPLE_ORDER,
    "items": [
        {
            "menu_name_snapshot": "Nasi Goreng",
            "menu_price_snapshot": "15000",
            "quantity": 2,
            "subtotal": "30000",
        }
    ],
}

VALID_CREATE_BODY = {
    "buyer_name": "Budi",
    "items": [{"menu_id": "aaaaaaaa-0000-0000-0000-000000000001", "quantity": 2}],
    "notes": "Extra spicy",
}

# Minimal valid JPEG magic bytes (just enough to pass the magic check)
JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100


# ---------------------------------------------------------------------------
# 1. test_create_order_success
# ---------------------------------------------------------------------------


async def test_create_order_success(client: AsyncClient):
    """Valid request → 201, response contains tracking_token."""
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=(SAMPLE_ORDER, "plain-token-abc", False)),
    ):
        resp = await client.post("/orders", json=VALID_CREATE_BODY)

    assert resp.status_code == 201
    data = resp.json()
    assert data["order_number"] == "ORD-20240101-ABCD"
    assert data["tracking_token"] == "plain-token-abc"
    assert "message" in data


# ---------------------------------------------------------------------------
# 2. test_create_order_idempotency_duplicate
# ---------------------------------------------------------------------------


async def test_create_order_idempotency_duplicate(client: AsyncClient):
    """Duplicate idempotency key → 200, NO tracking_token."""
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=(SAMPLE_ORDER, None, True)),
    ):
        resp = await client.post(
            "/orders",
            json=VALID_CREATE_BODY,
            headers={"Idempotency-Key": "some-key-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "tracking_token" not in data
    assert data["order_number"] == "ORD-20240101-ABCD"


# ---------------------------------------------------------------------------
# 3. test_create_order_unavailable_menu
# ---------------------------------------------------------------------------


async def test_create_order_unavailable_menu(client: AsyncClient):
    """Service raises 400 MENU_NOT_AVAILABLE → router returns 400."""
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "MENU_NOT_AVAILABLE",
                        "message": "Menu is not available: Nasi Goreng",
                    }
                },
            )
        ),
    ):
        resp = await client.post("/orders", json=VALID_CREATE_BODY)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MENU_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 4. test_create_order_inactive_menu
# ---------------------------------------------------------------------------


async def test_create_order_inactive_menu(client: AsyncClient):
    """Service raises 400 MENU_NOT_ACTIVE → router returns 400."""
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "MENU_NOT_ACTIVE",
                        "message": "Menu is not active: Nasi Goreng",
                    }
                },
            )
        ),
    ):
        resp = await client.post("/orders", json=VALID_CREATE_BODY)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MENU_NOT_ACTIVE"


# ---------------------------------------------------------------------------
# 5. test_create_order_empty_items
# ---------------------------------------------------------------------------


async def test_create_order_empty_items(client: AsyncClient):
    """Empty items list → 422 validation error."""
    resp = await client.post(
        "/orders", json={"buyer_name": "Budi", "items": []}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. test_create_order_zero_quantity
# ---------------------------------------------------------------------------


async def test_create_order_zero_quantity(client: AsyncClient):
    """quantity=0 → 422 validation error."""
    resp = await client.post(
        "/orders",
        json={
            "buyer_name": "Budi",
            "items": [{"menu_id": "aaaaaaaa-0000-0000-0000-000000000001", "quantity": 0}],
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. test_create_order_empty_name
# ---------------------------------------------------------------------------


async def test_create_order_empty_name(client: AsyncClient):
    """buyer_name="" → 422 validation error."""
    resp = await client.post(
        "/orders",
        json={
            "buyer_name": "",
            "items": [{"menu_id": "aaaaaaaa-0000-0000-0000-000000000001", "quantity": 1}],
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. test_create_order_price_not_in_request
# ---------------------------------------------------------------------------


async def test_create_order_price_not_in_request(client: AsyncClient):
    """OrderCreateRequest has extra='forbid'; sending a price field → 422."""
    resp = await client.post(
        "/orders",
        json={
            "buyer_name": "Budi",
            "items": [
                {
                    "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "quantity": 1,
                    "price": 99999,  # should be rejected
                }
            ],
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. test_upload_proof_success
# ---------------------------------------------------------------------------


async def test_upload_proof_success(client: AsyncClient):
    """Valid token + valid JPEG file → 200, payment_status=pending_verification."""
    updated_order = {**SAMPLE_ORDER, "payment_status": "pending_verification"}
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(return_value=updated_order),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_status"] == "pending_verification"


# ---------------------------------------------------------------------------
# 10. test_upload_proof_wrong_token
# ---------------------------------------------------------------------------


async def test_upload_proof_wrong_token(client: AsyncClient):
    """Wrong X-Tracking-Token → 403."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=403,
                detail={"error": {"code": "FORBIDDEN", "message": "Invalid tracking token"}},
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": "wrong-token"},
        )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# 11. test_upload_proof_missing_token_header
# ---------------------------------------------------------------------------


async def test_upload_proof_missing_token_header(client: AsyncClient):
    """No X-Tracking-Token header → 422."""
    resp = await client.post(
        "/orders/ORD-20240101-ABCD/proof",
        files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
        # No X-Tracking-Token header
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 12. test_upload_proof_already_paid
# ---------------------------------------------------------------------------


async def test_upload_proof_already_paid(client: AsyncClient):
    """payment_status=paid → 409 PROOF_UPLOAD_NOT_ALLOWED."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "PROOF_UPLOAD_NOT_ALLOWED",
                        "message": "Pembayaran sudah diverifikasi atau ditolak",
                    }
                },
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROOF_UPLOAD_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 13. test_upload_proof_rejected
# ---------------------------------------------------------------------------


async def test_upload_proof_rejected(client: AsyncClient):
    """payment_status=rejected → 409 PROOF_UPLOAD_NOT_ALLOWED."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "PROOF_UPLOAD_NOT_ALLOWED",
                        "message": "Pembayaran sudah diverifikasi atau ditolak",
                    }
                },
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROOF_UPLOAD_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 14. test_upload_proof_cancelled_order
# ---------------------------------------------------------------------------


async def test_upload_proof_cancelled_order(client: AsyncClient):
    """order_status=cancelled → 409 PROOF_UPLOAD_NOT_ALLOWED."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "PROOF_UPLOAD_NOT_ALLOWED",
                        "message": "Pesanan sudah dibatalkan",
                    }
                },
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROOF_UPLOAD_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 15. test_upload_proof_invalid_file_type
# ---------------------------------------------------------------------------


async def test_upload_proof_invalid_file_type(client: AsyncClient):
    """text/plain file → 400 INVALID_FILE_TYPE."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_FILE_TYPE",
                        "message": "File must be JPEG, PNG, or WebP",
                    }
                },
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("proof.txt", BytesIO(b"not an image"), "text/plain")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


# ---------------------------------------------------------------------------
# 16. test_upload_proof_file_too_large
# ---------------------------------------------------------------------------


async def test_upload_proof_file_too_large(client: AsyncClient):
    """6 MB file → 400 FILE_TOO_LARGE."""
    with patch(
        "routers.order.order_service.upload_proof",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": "File must not exceed 5 MB",
                    }
                },
            )
        ),
    ):
        resp = await client.post(
            "/orders/ORD-20240101-ABCD/proof",
            files={"file": ("big.jpg", BytesIO(b"\xff\xd8\xff" + b"\x00" * (6 * 1024 * 1024)), "image/jpeg")},
            headers={"X-Tracking-Token": "plain-token-abc"},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


# ---------------------------------------------------------------------------
# 17. test_track_order_success
# ---------------------------------------------------------------------------


async def test_track_order_success(client: AsyncClient):
    """Valid token → 200 with order + items."""
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(return_value=SAMPLE_ORDER_WITH_ITEMS),
    ):
        resp = await client.get("/orders/track/valid-token-abc")

    assert resp.status_code == 200
    data = resp.json()
    assert data["order_number"] == "ORD-20240101-ABCD"
    assert data["buyer_name"] == "Budi"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# 18. test_track_order_invalid_token
# ---------------------------------------------------------------------------


async def test_track_order_invalid_token(client: AsyncClient):
    """Wrong tracking token → 404 INVALID_TRACKING_TOKEN."""
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "INVALID_TRACKING_TOKEN",
                        "message": "Order not found",
                    }
                },
            )
        ),
    ):
        resp = await client.get("/orders/track/wrong-token")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INVALID_TRACKING_TOKEN"


# ---------------------------------------------------------------------------
# 19. test_track_order_rate_limit_not_broken
# ---------------------------------------------------------------------------


async def test_track_order_rate_limit_not_broken(client: AsyncClient):
    """A single call to track endpoint works → 200 (rate limit not triggered)."""
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(return_value=SAMPLE_ORDER_WITH_ITEMS),
    ):
        resp = await client.get("/orders/track/any-token")

    assert resp.status_code == 200
