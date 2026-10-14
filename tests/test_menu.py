"""
Tests for all Menu API endpoints (Sub-Task 4).

Service functions are mocked at the service layer so no real Supabase
connection is required.
"""
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_seller_jwt, make_wrong_jwt, TEST_SELLER_UID

# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

MENU_1 = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "name": "Nasi Goreng",
    "description": "Delicious fried rice",
    "price": "15000",
    "image_url": "https://example.com/nasi-goreng.jpg",
    "menu_type": "Makanan",
    "category": "Nasi",
    "is_available": True,
    "is_active": True,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
}

MENU_2 = {
    "id": "aaaaaaaa-0000-0000-0000-000000000002",
    "name": "Es Teh",
    "description": "Iced sweet tea",
    "price": "5000",
    "image_url": None,
    "menu_type": "Minuman",
    "category": "Minuman Dingin",
    "is_available": True,
    "is_active": True,
    "created_at": "2024-01-02T00:00:00",
    "updated_at": "2024-01-02T00:00:00",
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _seller_auth_header() -> dict:
    return {"Authorization": f"Bearer {make_seller_jwt()}"}

def _wrong_auth_header() -> dict:
    return {"Authorization": f"Bearer {make_wrong_jwt()}"}


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


async def test_get_menus_returns_list(client: AsyncClient):
    """Mock returns 2 menus (including unavailable); response body is a list of 2."""
    with patch(
        "routers.menu.get_menus",
        new_callable=AsyncMock,
        return_value=[MENU_1, MENU_2],
    ):
        response = await client.get("/menus")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Nasi Goreng"
    assert data[0]["menu_type"] == "Makanan"
    assert data[1]["name"] == "Es Teh"
    assert data[1]["menu_type"] == "Minuman"


async def test_get_menus_empty(client: AsyncClient):
    """Mock returns empty list; response body is []."""
    with patch(
        "routers.menu.get_menus",
        new_callable=AsyncMock,
        return_value=[],
    ):
        response = await client.get("/menus")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_menu_detail_found(client: AsyncClient):
    """Mock returns MENU_1; response has correct fields."""
    with patch(
        "routers.menu.get_menu_detail",
        new_callable=AsyncMock,
        return_value=MENU_1,
    ):
        response = await client.get(f"/menus/{MENU_1['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == MENU_1["id"]
    assert data["name"] == "Nasi Goreng"
    assert data["is_active"] is True


async def test_get_menu_detail_not_found(client: AsyncClient):
    """Service raises 404; response is 404 with MENU_NOT_FOUND."""
    from fastapi import HTTPException

    with patch(
        "routers.menu.get_menu_detail",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        ),
    ):
        response = await client.get("/menus/nonexistent-id")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MENU_NOT_FOUND"


# ---------------------------------------------------------------------------
# Seller create menu
# ---------------------------------------------------------------------------


async def test_create_menu_requires_auth(client: AsyncClient):
    """No Authorization header → 401."""
    response = await client.post(
        "/seller/menus",
        json={"name": "Test", "price": "10000"},
    )
    assert response.status_code == 401


async def test_create_menu_wrong_uid(client: AsyncClient):
    """Valid JWT but wrong UID → 403."""
    response = await client.post(
        "/seller/menus",
        json={"name": "Test", "price": "10000"},
        headers=_wrong_auth_header(),
    )
    assert response.status_code == 403


async def test_create_menu_success(client: AsyncClient):
    """Valid seller JWT + mocked service → 201 with menu data including menu_type."""
    with patch(
        "routers.seller.create_menu",
        new_callable=AsyncMock,
        return_value=MENU_1,
    ):
        response = await client.post(
            "/seller/menus",
            json={"name": "Nasi Goreng", "price": "15000", "menu_type": "Makanan"},
            headers=_seller_auth_header(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nasi Goreng"
    assert data["id"] == MENU_1["id"]
    assert data["menu_type"] == "Makanan"


async def test_create_menu_invalid_price(client: AsyncClient):
    """price=0 → 422 VALIDATION_ERROR."""
    response = await client.post(
        "/seller/menus",
        json={"name": "Test", "price": "0"},
        headers=_seller_auth_header(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_menu_empty_name(client: AsyncClient):
    """name="" → 422 VALIDATION_ERROR."""
    response = await client.post(
        "/seller/menus",
        json={"name": "", "price": "10000"},
        headers=_seller_auth_header(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Seller update menu
# ---------------------------------------------------------------------------


async def test_update_menu_requires_auth(client: AsyncClient):
    """No auth → 401."""
    response = await client.patch(
        f"/seller/menus/{MENU_1['id']}",
        json={"name": "New Name"},
    )
    assert response.status_code == 401


async def test_update_menu_success(client: AsyncClient):
    """Valid auth + partial update → 200 with updated menu."""
    updated = {**MENU_1, "name": "Nasi Goreng Spesial"}
    with patch(
        "routers.seller.update_menu",
        new_callable=AsyncMock,
        return_value=updated,
    ):
        response = await client.patch(
            f"/seller/menus/{MENU_1['id']}",
            json={"name": "Nasi Goreng Spesial"},
            headers=_seller_auth_header(),
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Nasi Goreng Spesial"


async def test_set_availability_toggle(client: AsyncClient):
    """Valid auth, is_available=false → 200 with updated menu."""
    updated = {**MENU_1, "is_available": False}
    with patch(
        "routers.seller.set_availability",
        new_callable=AsyncMock,
        return_value=updated,
    ):
        response = await client.patch(
            f"/seller/menus/{MENU_1['id']}/availability",
            json={"is_available": False},
            headers=_seller_auth_header(),
        )

    assert response.status_code == 200
    assert response.json()["is_available"] is False


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


async def test_upload_image_requires_auth(client: AsyncClient):
    """No auth → 401."""
    jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 10
    response = await client.post(
        "/seller/menus/upload-image",
        files={"file": ("test.jpg", BytesIO(jpeg_bytes), "image/jpeg")},
    )
    assert response.status_code == 401


async def test_upload_image_invalid_type(client: AsyncClient):
    """Wrong content_type → 400 INVALID_FILE_TYPE."""
    response = await client.post(
        "/seller/menus/upload-image",
        files={"file": ("test.txt", BytesIO(b"hello world"), "text/plain")},
        headers=_seller_auth_header(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


async def test_upload_image_too_large(client: AsyncClient):
    """File > 5MB → 400 FILE_TOO_LARGE."""
    # Create valid JPEG magic bytes followed by > 5MB of padding
    large_bytes = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024 + 1)
    response = await client.post(
        "/seller/menus/upload-image",
        files={"file": ("big.jpg", BytesIO(large_bytes), "image/jpeg")},
        headers=_seller_auth_header(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_upload_image_success(client: AsyncClient):
    """Valid JPEG + mocked service → 200 with image_url."""
    jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 100
    expected_url = "https://test.supabase.co/storage/v1/object/public/menu-images/abc.jpg"

    with patch(
        "routers.seller.upload_menu_image",
        new_callable=AsyncMock,
        return_value=expected_url,
    ):
        response = await client.post(
            "/seller/menus/upload-image",
            files={"file": ("photo.jpg", BytesIO(jpeg_bytes), "image/jpeg")},
            headers=_seller_auth_header(),
        )

    assert response.status_code == 200
    assert response.json()["image_url"] == expected_url
