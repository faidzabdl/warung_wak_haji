import hashlib
import secrets
import string
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException

from db import get_service_client
from schemas.order import OrderCreateRequest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ORDER_NUMBER_CHARS = string.ascii_uppercase + string.digits


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode()).hexdigest()


def _generate_order_number() -> str:
    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    suffix = "".join(secrets.choice(_ORDER_NUMBER_CHARS) for _ in range(4))
    return f"ORD-{date_str}-{suffix}"


# ---------------------------------------------------------------------------
# create_order
# ---------------------------------------------------------------------------


async def create_order(
    request: OrderCreateRequest,
    idempotency_key: str | None,
) -> tuple[dict, str | None, bool]:
    """Create a new order.

    Returns:
        (order_dict, plain_token, is_duplicate)
        - plain_token is None when is_duplicate=True
    """
    client = get_service_client()

    # 1. Idempotency check
    if idempotency_key:
        resp = (
            client.table("orders")
            .select("*")
            .eq("idempotency_key", idempotency_key)
            .maybe_single()
            .execute()
        )
        if resp is not None and resp.data:
            return (resp.data, None, True)

    # 2. Generate tracking token
    plain_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(plain_token)

    # 3. Build order payload — status determined by RPC based on payment_method
    order_payload = {
        "buyer_name": request.buyer_name,
        "table_number": request.table_number,
        "payment_method": request.payment_method,
        "notes": request.notes,
        "tracking_token_hash": token_hash,
        "idempotency_key": idempotency_key,
    }

    # 4. Build items payload — price and menu_type fetched by RPC from DB
    order_items_data = [
        {
            "menu_id": item.menu_id,
            "quantity": item.quantity,
        }
        for item in request.items
    ]

    # 5. Generate order_number with retry on collision
    for _ in range(3):
        order_number = _generate_order_number()
        order_payload["order_number"] = order_number
        try:
            result = client.rpc(
                "create_order_with_items",
                {"order_data": order_payload, "items_data": order_items_data},
            ).execute()
            order_dict = result.data
            if isinstance(order_dict, list):
                order_dict = order_dict[0]
            return (order_dict, plain_token, False)
        except Exception as exc:
            msg = str(exc).lower()
            if "unique" in msg and "order_number" in msg:
                continue
            # Re-raise with appropriate HTTP status for menu validation errors
            if "menu not found" in msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "MENU_NOT_FOUND",
                            "message": str(exc),
                        }
                    },
                )
            if "menu not available" in msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "MENU_NOT_AVAILABLE",
                            "message": str(exc),
                        }
                    },
                )
            if "menu not active" in msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "MENU_NOT_ACTIVE",
                            "message": str(exc),
                        }
                    },
                )
            raise

    raise HTTPException(
        status_code=500,
        detail={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to generate unique order number",
            }
        },
    )


# ---------------------------------------------------------------------------
# track_order
# ---------------------------------------------------------------------------


async def track_order(plain_token: str) -> dict:
    """Return order details for a given tracking token."""
    token_hash = _hash_token(plain_token)
    client = get_service_client()

    # 1. Lookup order by token hash
    resp = (
        client.table("orders")
        .select("*")
        .eq("tracking_token_hash", token_hash)
        .maybe_single()
        .execute()
    )
    if resp is None or not resp.data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "INVALID_TRACKING_TOKEN",
                    "message": "Order not found",
                }
            },
        )
    order = resp.data

    # 2. Fetch order items
    items_resp = (
        client.table("order_items")
        .select("menu_name_snapshot, menu_price_snapshot, menu_type, quantity, subtotal, menu_id")
        .eq("order_id", order["id"])
        .execute()
    )
    order["items"] = items_resp.data or []
    return order
