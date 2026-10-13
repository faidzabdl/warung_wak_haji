# conftest.py — pytest fixtures and configuration for the UMKM Ordering API test suite.
#
# asyncio_mode = auto is set in pytest.ini so all async tests run without
# explicit @pytest.mark.asyncio decorators.
#
# Env vars MUST be set before any app import so that config.py / get_settings()
# picks them up. We also clear the lru_cache so a re-import reloads settings.

import os
import time

# ---------------------------------------------------------------------------
# Inject test environment variables BEFORE importing the app
# ---------------------------------------------------------------------------
# These values are test-only and match constants used in test_auth.py:
#   JWT_SECRET = "test-secret"
#   SELLER_UID = "00000000-0000-0000-0000-000000000001"

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ALLOWED_SELLER_UID", "00000000-0000-0000-0000-000000000001")
os.environ.setdefault("ENVIRONMENT", "test")

# Clear cached settings so the injected env vars take effect
from config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest  # noqa: E402
import jwt as pyjwt  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Test constants — must match values injected above
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret"
TEST_SELLER_UID = "00000000-0000-0000-0000-000000000001"
TEST_OTHER_UID = "00000000-0000-0000-0000-000000000002"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def make_seller_jwt(uid: str = TEST_SELLER_UID) -> str:
    """Generate a valid HS256 JWT for the given seller UID."""
    now = int(time.time())
    payload = {
        "sub": uid,
        "aud": "authenticated",
        "iat": now - 10,
        "exp": now + 3600,
    }
    return pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def make_wrong_jwt() -> str:
    """Generate a valid HS256 JWT with a UID that is NOT the allowed seller."""
    return make_seller_jwt(uid=TEST_OTHER_UID)


# ---------------------------------------------------------------------------
# App-level client (no auth) — used for public endpoints and smoke tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired directly to the FastAPI app (no real network)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
