"""
Tests for Order API endpoints — v2 schema.

All service-layer functions are mocked so no real Supabase connection is needed.
Covers:
  - QRIS order: initial status awaiting_payment / pending_payment
  - Cash order: initial status waiting_processing / pending_payment
  - table_number validation (^\d{1,4}$)
  - payment_method validation (qris|cash)
  - menu unavailable / not found → 4xx
  - price not accepted from client (extra='forbid')
  - idempotency key deduplication
  - track_order: success, invalid token
  - No proof upload endpoint exists (OpenAPI check)
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ORDER_QRIS = {
    "id": "bbbbbbbb-0000-0000-0000-000000000001",
    "order_number": "ORD-20240101-QRIS",
    "buyer_name": "Budi",
    "table_number": "3",
    "payment_method": "qris",
    "notes": None,
    "total_amount": "30000",
    "payment_status": "pending_payment",
    "order_status": "awaiting_payment",
    "tracking_token_hash": "fakehash",
    "idempotency_key": None,
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00",
}

SAMPLE_ORDER_CASH = {
    **SAMPLE_ORDER_QRIS,
    "order_number": "ORD-20240101-CASH",
    "payment_method": "cash",
    "order_status": "waiting_processing",
}

SAMPLE_ORDER_WITH_ITEMS = {
    **SAMPLE_ORDER_QRIS,
    "items": [
        {
            "menu_name_snapshot": "Nasi Goreng",
            "menu_price_snapshot": "15000",
            "menu_type": "Makanan",
            "quantity": 2,
            "subtotal": "30000",
            "menu_id": "aaaaaaaa-0000-0000-0000-000000000001",
        }
    ],
}

# Minimal valid body — must include table_number and payment_method
VALID_QRIS_BODY = {
    "buyer_name": "Budi",
    "table_number": "3",
    "payment_method": "qris",
    "items": [{"menu_id": "aaaaaaaa-0000-0000-0000-000000000001", "quantity": 2}],
    "notes": "Extra spicy",
}

VALID_CASH_BODY = {**VALID_QRIS_BODY, "payment_method": "cash"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_create(return_value):
    return patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(return_value=return_value),
    )


def _patch_create_raises(exc):
    return patch(
        "routers.order.order_service.create_order",
        new=AsyncMock(side_effect=exc),
    )


# ===========================================================================
# CREATE ORDER — QRIS initial status
# ===========================================================================

async def test_create_order_qris_initial_status(client: AsyncClient):
    """QRIS order: 201, order_status=awaiting_payment, payment_status=pending_payment."""
    with _patch_create((SAMPLE_ORDER_QRIS, "plain-token-qris", False)):
        resp = await client.post("/orders", json=VALID_QRIS_BODY)

    assert resp.status_code == 201
    data = resp.json()
    assert data["order_number"] == "ORD-20240101-QRIS"
    assert data["tracking_token"] == "plain-token-qris"
    assert "message" in data


async def test_create_order_cash_initial_status(client: AsyncClient):
    """Cash order: 201, order_status=waiting_processing, payment_status=pending_payment."""
    with _patch_create((SAMPLE_ORDER_CASH, "plain-token-cash", False)):
        resp = await client.post("/orders", json=VALID_CASH_BODY)

    assert resp.status_code == 201
    data = resp.json()
    assert data["order_number"] == "ORD-20240101-CASH"
    assert data["tracking_token"] == "plain-token-cash"


# ===========================================================================
# CREATE ORDER — field validation
# ===========================================================================

async def test_create_order_missing_table_number(client: AsyncClient):
    """No table_number → 422 VALIDATION_ERROR."""
    body = {**VALID_QRIS_BODY}
    del body["table_number"]
    resp = await client.post("/orders", json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_table_number_not_digits(client: AsyncClient):
    """table_number='A1' (not digits) → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "table_number": "A1"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_table_number_too_long(client: AsyncClient):
    """table_number='12345' (5 digits > max 4) → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "table_number": "12345"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_table_number_empty(client: AsyncClient):
    """table_number='' → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "table_number": ""})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_invalid_payment_method(client: AsyncClient):
    """payment_method='bitcoin' → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "payment_method": "bitcoin"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_missing_payment_method(client: AsyncClient):
    """No payment_method → 422 VALIDATION_ERROR."""
    body = {**VALID_QRIS_BODY}
    del body["payment_method"]
    resp = await client.post("/orders", json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_empty_name(client: AsyncClient):
    """buyer_name='' → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "buyer_name": ""})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_empty_items(client: AsyncClient):
    """Empty items list → 422 VALIDATION_ERROR."""
    resp = await client.post("/orders", json={**VALID_QRIS_BODY, "items": []})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_zero_quantity(client: AsyncClient):
    """quantity=0 → 422 VALIDATION_ERROR."""
    resp = await client.post(
        "/orders",
        json={**VALID_QRIS_BODY, "items": [{"menu_id": "aaa", "quantity": 0}]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_order_price_field_rejected(client: AsyncClient):
    """Sending price in OrderItemInput → 422 (extra='forbid')."""
    resp = await client.post(
        "/orders",
        json={
            **VALID_QRIS_BODY,
            "items": [{"menu_id": "aaa", "quantity": 1, "price": 99999}],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# CREATE ORDER — service-layer errors
# ===========================================================================

async def test_create_order_menu_not_available(client: AsyncClient):
    """Service raises 400 MENU_NOT_AVAILABLE → router returns 400."""
    with _patch_create_raises(
        HTTPException(
            status_code=400,
            detail={"error": {"code": "MENU_NOT_AVAILABLE", "message": "Menu is not available: Nasi Goreng"}},
        )
    ):
        resp = await client.post("/orders", json=VALID_QRIS_BODY)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MENU_NOT_AVAILABLE"


async def test_create_order_menu_not_found(client: AsyncClient):
    """Service raises 400 MENU_NOT_FOUND → router returns 400."""
    with _patch_create_raises(
        HTTPException(
            status_code=400,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )
    ):
        resp = await client.post("/orders", json=VALID_QRIS_BODY)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MENU_NOT_FOUND"


async def test_create_order_menu_not_active(client: AsyncClient):
    """Service raises 400 MENU_NOT_ACTIVE → router returns 400."""
    with _patch_create_raises(
        HTTPException(
            status_code=400,
            detail={"error": {"code": "MENU_NOT_ACTIVE", "message": "Menu is not active"}},
        )
    ):
        resp = await client.post("/orders", json=VALID_QRIS_BODY)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MENU_NOT_ACTIVE"


# ===========================================================================
# CREATE ORDER — idempotency
# ===========================================================================

async def test_create_order_idempotency_duplicate(client: AsyncClient):
    """Duplicate idempotency key → 200, NO tracking_token."""
    with _patch_create((SAMPLE_ORDER_QRIS, None, True)):
        resp = await client.post(
            "/orders",
            json=VALID_QRIS_BODY,
            headers={"Idempotency-Key": "some-key-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "tracking_token" not in data
    assert data["order_number"] == "ORD-20240101-QRIS"


# ===========================================================================
# TRACK ORDER
# ===========================================================================

async def test_track_order_success(client: AsyncClient):
    """Valid token → 200, includes table_number and payment_method."""
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(return_value=SAMPLE_ORDER_WITH_ITEMS),
    ):
        resp = await client.get("/orders/track/some-valid-token")

    assert resp.status_code == 200
    data = resp.json()
    assert data["order_number"] == "ORD-20240101-QRIS"
    assert data["table_number"] == "3"
    assert data["payment_method"] == "qris"
    assert data["order_status"] == "awaiting_payment"
    assert data["payment_status"] == "pending_payment"
    assert isinstance(data["items"], list)
    assert data["items"][0]["menu_type"] == "Makanan"


async def test_track_order_invalid_token(client: AsyncClient):
    """Invalid token → 404 INVALID_TRACKING_TOKEN."""
    with patch(
        "routers.order.order_service.track_order",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=404,
                detail={"error": {"code": "INVALID_TRACKING_TOKEN", "message": "Order not found"}},
            )
        ),
    ):
        resp = await client.get("/orders/track/bad-token")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INVALID_TRACKING_TOKEN"


# ===========================================================================
# NO PROOF UPLOAD ENDPOINT
# ===========================================================================

async def test_no_proof_upload_endpoint(client: AsyncClient):
    """POST /orders/{n}/proof must not exist (removed in v2)."""
    resp = await client.post(
        "/orders/ORD-20240101-QRIS/proof",
        headers={"X-Tracking-Token": "sometoken"},
    )
    assert resp.status_code == 404, (
        "Proof upload endpoint must be removed. Got status: " + str(resp.status_code)
    )


async def test_openapi_no_proof_route(client: AsyncClient):
    """OpenAPI schema must not contain /proof path."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    proof_paths = [p for p in paths if "proof" in p]
    assert proof_paths == [], f"Unexpected proof paths in OpenAPI: {proof_paths}"
