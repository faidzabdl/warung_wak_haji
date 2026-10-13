"""
Tests for the require_seller dependency.

These tests use a dummy SUPABASE_JWT_SECRET ("test-secret") that matches the
value injected by the test environment. We generate tokens with PyJWT directly
to keep tests self-contained and network-free.
"""
import time

import jwt
import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper — create a test endpoint that uses require_seller
# ---------------------------------------------------------------------------

from fastapi import Depends
from main import app
from dependencies.auth import require_seller


@app.get("/test/seller-only", tags=["Test"], include_in_schema=False)
async def _seller_only(uid: str = Depends(require_seller)):
    return {"uid": uid}


JWT_SECRET = "test-secret"
SELLER_UID = "00000000-0000-0000-0000-000000000001"
OTHER_UID = "00000000-0000-0000-0000-000000000002"


def _make_token(sub: str, secret: str = JWT_SECRET, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "iat": now - 10,
        "exp": now - 5 if expired else now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_no_auth_header_returns_401(client: AsyncClient):
    response = await client.get("/test/seller-only")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_malformed_header_returns_401(client: AsyncClient):
    response = await client.get(
        "/test/seller-only", headers={"Authorization": "Token abc"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_expired_token_returns_401(client: AsyncClient):
    token = _make_token(SELLER_UID, expired=True)
    response = await client.get(
        "/test/seller-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_invalid_signature_returns_401(client: AsyncClient):
    token = _make_token(SELLER_UID, secret="wrong-secret")
    response = await client.get(
        "/test/seller-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_wrong_uid_returns_403(client: AsyncClient):
    token = _make_token(OTHER_UID)
    response = await client.get(
        "/test/seller-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_valid_seller_token_returns_200(client: AsyncClient):
    token = _make_token(SELLER_UID)
    response = await client.get(
        "/test/seller-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["uid"] == SELLER_UID
