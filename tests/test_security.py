"""
Security-specific tests for the UMKM Ordering API.

Coverage notes
--------------
Auth bypass scenarios (no header / malformed header / expired / invalid
signature / wrong UID) are already fully covered in tests/test_auth.py and
are NOT duplicated here.  Each relevant section carries a comment pointing
to the authoritative location.

Re-upload guard scenarios (paid / rejected / cancelled) are already covered
in tests/test_orders.py (test_upload_proof_already_paid,
test_upload_proof_rejected, test_upload_proof_cancelled_order).  They are
NOT duplicated here.

Tracking-token lookup with a random/wrong token is covered in
tests/test_orders.py (test_track_order_invalid_token).

This file focuses on:
  1. Input manipulation — extra/forbidden fields in OrderCreateRequest
  2. Token security — variant token attacks not covered elsewhere
  3. Seller-endpoint UID enforcement on mutating actions
  4. Idempotency contract (security dimension: no new token on duplicate)
"""
import time
from io import BytesIO
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from tests.conftest import (
    TEST_JWT_SECRET,
    TEST_OTHER_UID,
    TEST_SELLER_UID,
    make_seller_jwt,
    make_wrong_jwt,
)

# ---------------------------------------------------------------------------
# Constants / shared fixtures
# ---------------------------------------------------------------------------

_ORDER_NUMBER = "ORD-20240101-ABCD"
# Unique order numbers for re-upload guard tests so the slowapi rate limiter
# (10/min on proof uploads) shared with test_orders.py does not overflow.
_ORDER_PAID     = "ORD-20240101-PAID"
_ORDER_REJECTED = "ORD-20240101-RJCT"
_ORDER_CANCEL   = "ORD-20240101-CNCL"

_SAMPLE_ORDER = {
    "id": "bbbbbbbb-0000-0000-0000-000000000001",
    "order_number": _ORDER_NUMBER,
    "buyer_name": "Budi",
    "table_number": "5",
    "payment_method": "qris",
    "notes": None,
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "15000",
    "tracking_token_hash": "somehash",
    "idempotency_key": "idem-key-001",
    "cancel_reason": None,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
}

_VALID_BODY = {
    "buyer_name": "Budi",
    "table_number": "5",
    "payment_method": "qris",
    "items": [{"menu_id": "aaaaaaaa-0000-0000-0000-000000000001", "quantity": 2}],
}

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100


def _auth(uid: str = TEST_SELLER_UID) -> dict:
    """Return Authorization header for the given UID."""
    token = make_seller_jwt(uid)
    return {"Authorization": f"Bearer {token}"}


def _wrong_auth() -> dict:
    return {"Authorization": f"Bearer {make_wrong_jwt()}"}


# ===========================================================================
# Section 1 — Auth bypass
# (Authoritative tests live in tests/test_auth.py)
# ===========================================================================
# test_valid_jwt_wrong_uid_returns_403   → test_auth.py::test_wrong_uid_returns_403
# test_expired_jwt_returns_401           → test_auth.py::test_expired_token_returns_401
# test_missing_auth_header_returns_401   → test_auth.py::test_no_auth_header_returns_401
# test_malformed_header_returns_401      → test_auth.py::test_malformed_header_returns_401


async def test_garbage_bearer_payload_returns_401(client: AsyncClient):
    """
    Authorization header is properly formatted ('Bearer <token>') but the
    token value is pure garbage — not a JWT at all.

    test_auth.py::test_malformed_header_returns_401 tests a missing 'Bearer '
    prefix.  This complementary test confirms that a correctly-shaped header
    with an invalid token body also returns 401 INVALID_TOKEN.
    """
    response = await client.get(
        "/test/seller-only",
        headers={"Authorization": "Bearer this.is.garbage"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


# ===========================================================================
# Section 2 — Input manipulation: forbidden extra fields on OrderCreateRequest
# ===========================================================================
# OrderCreateRequest uses model_config = ConfigDict(extra="forbid").
# Pydantic should raise a ValidationError (→ 422) for any unrecognised field.
#
# test_orders.py::test_create_order_price_not_in_request already covers a
# 'price' field on the *item* sub-object (OrderItemInput also has extra=forbid).
# The tests below cover forbidden fields at the *order root* level.


async def test_order_create_ignores_total_field(client: AsyncClient):
    """
    Sending 'total_amount' in the order body is rejected with 422.
    Buyers must not be able to inject a pre-computed total.
    """
    body = {**_VALID_BODY, "total_amount": 999999}
    response = await client.post("/orders", json=body)
    assert response.status_code == 422


async def test_order_create_ignores_status_field(client: AsyncClient):
    """Sending 'order_status' in the order body is rejected with 422."""
    body = {**_VALID_BODY, "order_status": "completed"}
    response = await client.post("/orders", json=body)
    assert response.status_code == 422


async def test_order_create_ignores_role_field(client: AsyncClient):
    """Sending a 'role' field in the order body is rejected with 422."""
    body = {**_VALID_BODY, "role": "admin"}
    response = await client.post("/orders", json=body)
    assert response.status_code == 422


async def test_order_create_ignores_payment_status_field(client: AsyncClient):
    """Sending 'payment_status' in the order body is rejected with 422."""
    body = {**_VALID_BODY, "payment_status": "paid"}
    response = await client.post("/orders", json=body)
    assert response.status_code == 422


async def test_order_create_ignores_price_on_item(client: AsyncClient):
    """
    Sending a 'price' field inside an order item is rejected with 422.
    (OrderItemInput also has extra='forbid'; this is the root-security variant
    that focuses on the *item-level* price injection attack.)

    Note: test_orders.py::test_create_order_price_not_in_request covers the
    same schema path.  This test is retained here as a security-catalogue entry
    so that test_security.py is a self-contained reference.
    """
    body = {
        "buyer_name": "Budi",
        "items": [
            {
                "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "quantity": 1,
                "price": 99999,  # must be rejected
            }
        ],
    }
    response = await client.post("/orders", json=body)
    assert response.status_code == 422


# ===========================================================================
# Section 3 — Token security
# ===========================================================================
# test_orders.py::test_track_order_invalid_token covers random-token → 404.
# Proof upload endpoint has been REMOVED — buyers no longer upload proof.
# QRIS verification is done entirely by the seller via verify-payment.


async def test_tracking_not_found_returns_404(client: AsyncClient):
    """
    A completely random string as a tracking token must return 404
    INVALID_TRACKING_TOKEN — not a 500 or any other leak.

    (This is the security-catalogue copy; authoritative test is in
    test_orders.py::test_track_order_invalid_token.)
    """
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
        response = await client.get("/orders/track/aaaaabbbbbccccc-random-garbage")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INVALID_TRACKING_TOKEN"


async def test_proof_upload_endpoint_removed(client: AsyncClient):
    """
    POST /orders/{num}/proof no longer exists — proof upload was removed.
    The endpoint must return 404 or 405 (not 500).
    """
    response = await client.post(
        f"/orders/{_ORDER_NUMBER}/proof",
        files={"file": ("proof.jpg", BytesIO(JPEG_MAGIC), "image/jpeg")},
        headers={"X-Tracking-Token": "any-token"},
    )
    assert response.status_code in (404, 405)


# ===========================================================================
# Section 4 — Proof upload endpoint removed
# ===========================================================================
# The /orders/{num}/proof endpoint has been deleted. Buyers no longer upload
# payment proof. QRIS is verified by the seller via verify-payment.
# The old re-upload guard tests (paid/rejected/cancelled) are no longer
# applicable and have been removed.


# ===========================================================================
# Section 5 — Idempotency contract (security dimension)
# ===========================================================================


async def test_idempotency_key_returns_existing_order_200(client: AsyncClient):
    """
    Sending an Idempotency-Key that was already used must return HTTP 200
    (not 201) and must NOT include a tracking_token in the response body.

    Security rationale: the plain tracking token is issued once only.  A
    duplicate request must never cause a second issuance or leak the original
    token value.
    """
    # Service signals is_duplicate=True by returning (order, None, True)
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=(_SAMPLE_ORDER, None, True)),
    ):
        response = await client.post(
            "/orders",
            json=_VALID_BODY,
            headers={"Idempotency-Key": "idem-key-001"},
        )

    assert response.status_code == 200
    data = response.json()
    # Duplicate responses must NOT include the plain tracking token
    assert "tracking_token" not in data
    assert data["order_number"] == _ORDER_NUMBER


async def test_no_idempotency_key_creates_new_order_201(client: AsyncClient):
    """
    Omitting the Idempotency-Key header allows a fresh order creation.
    Response is 201 and includes a tracking_token.
    """
    new_order = {**_SAMPLE_ORDER, "total_amount": "15000"}
    with patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=(new_order, "plain-token-xyz", False)),
    ):
        response = await client.post("/orders", json=_VALID_BODY)

    assert response.status_code == 201
    data = response.json()
    assert "tracking_token" in data
    assert data["tracking_token"] == "plain-token-xyz"


# ===========================================================================
# Section 6 — Seller-endpoint UID enforcement on mutating actions
# ===========================================================================
# test_auth.py covers the generic /test/seller-only route.
# These tests confirm that the *real* seller action endpoints also enforce
# the UID check, not just the test-helper route.


async def test_verify_payment_wrong_uid_returns_403(client: AsyncClient):
    """Valid JWT but wrong UID on POST /seller/orders/{num}/verify-payment → 403."""
    response = await client.post(
        f"/seller/orders/{_ORDER_NUMBER}/verify-payment",
        headers=_wrong_auth(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_start_processing_wrong_uid_returns_403(client: AsyncClient):
    """Valid JWT but wrong UID on POST /seller/orders/{num}/start-processing → 403."""
    response = await client.post(
        f"/seller/orders/{_ORDER_NUMBER}/start-processing",
        headers=_wrong_auth(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_complete_order_wrong_uid_returns_403(client: AsyncClient):
    """Valid JWT but wrong UID on POST /seller/orders/{num}/complete → 403."""
    response = await client.post(
        f"/seller/orders/{_ORDER_NUMBER}/complete",
        headers=_wrong_auth(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_cancel_order_wrong_uid_returns_403(client: AsyncClient):
    """Valid JWT but wrong UID on POST /seller/orders/{num}/cancel → 403."""
    response = await client.post(
        f"/seller/orders/{_ORDER_NUMBER}/cancel",
        json={"reason": "test"},
        headers=_wrong_auth(),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_seller_history_wrong_uid_returns_403(client: AsyncClient):
    """Valid JWT but wrong UID on GET /seller/history → 403."""
    response = await client.get("/seller/history", headers=_wrong_auth())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
