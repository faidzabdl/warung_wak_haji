import threading

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

from config import settings

# ---------------------------------------------------------------------------
# JWKS client — fetches and caches Supabase public keys automatically.
# PyJWT's PyJWKClient handles key rotation and caching.
# Supabase exposes JWKS at: <project_url>/auth/v1/.well-known/jwks.json
# ---------------------------------------------------------------------------

_jwks_client: PyJWKClient | None = None
_jwks_lock = threading.Lock()


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        with _jwks_lock:
            if _jwks_client is None:
                jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
                _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


async def require_seller(authorization: str = Header(None)) -> str:
    """
    Validates the Supabase JWT from the Authorization header and enforces
    ALLOWED_SELLER_UID.

    Supports both ES256 (new Supabase projects) and HS256 (legacy projects).
    The algorithm is determined from the token header — no hardcoding needed.

    Returns the seller uid (``sub`` claim) on success.
    Raises HTTPException(401) for missing / invalid / expired JWT.
    Raises HTTPException(403) for a valid JWT whose ``sub`` does not match
    ALLOWED_SELLER_UID.
    """
    # 1. Header must exist and start with "Bearer "
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing or malformed Authorization header"}},
        )

    token = authorization[len("Bearer "):]

    # 2. Peek at the token header to determine algorithm
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token is invalid"}},
        )

    alg = unverified_header.get("alg", "")

    # 3. Decode and verify
    try:
        if alg in ("ES256", "RS256"):
            # Asymmetric: verify using JWKS public key from Supabase
            jwks_client = _get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        else:
            # Legacy HS256: verify using SUPABASE_JWT_SECRET
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired"}},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token is invalid"}},
        )
    except Exception:
        # Catch JWKS fetch errors or key lookup failures
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token could not be verified"}},
        )

    # 4. Enforce single-seller UID
    sub: str = payload.get("sub", "")
    if sub != settings.allowed_seller_uid:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    return sub
