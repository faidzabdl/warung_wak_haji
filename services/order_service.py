import hashlib
import secrets
import string
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from db import get_service_client
from schemas.order import OrderCreateRequest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_MAGIC_BYTES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}

_ORDER_NUMBER_CHARS = string.ascii_uppercase + string.digits


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode()).hexdigest()


def _check_magic(content_type: str, data: bytes) -> bool:
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    magic = _MAGIC_BYTES.get(content_type)
    if magic is None:
        return False
    return data[: len(magic)] == magic


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
        - plain_token is None when is_duplicate=True (already issued, must not re-reveal)
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

    # 2. Validate menus
    menu_ids = [item.menu_id for item in request.items]
    menus_resp = client.table("menus").select("*").in_("id", menu_ids).execute()
    fetched_menus: dict[str, dict] = {m["id"]: m for m in (menus_resp.data or [])}

    for item in request.items:
        if item.menu_id not in fetched_menus:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "MENU_NOT_FOUND",
                        "message": f"Menu not found: {item.menu_id}",
                    }
                },
            )
        menu = fetched_menus[item.menu_id]
        if not menu.get("is_active", True):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "MENU_NOT_ACTIVE",
                        "message": f"Menu is not active: {menu['name']}",
                    }
                },
            )
        if not menu.get("is_available", True):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "MENU_NOT_AVAILABLE",
                        "message": f"Menu is not available: {menu['name']}",
                    }
                },
            )

    # 3. Calculate totals
    order_items_data = []
    total_amount = Decimal("0")
    for item in request.items:
        menu = fetched_menus[item.menu_id]
        price = Decimal(str(menu["price"]))
        subtotal = price * item.quantity
        total_amount += subtotal
        order_items_data.append(
            {
                "menu_id": item.menu_id,
                "menu_name_snapshot": menu["name"],
                "menu_price_snapshot": float(price),
                "quantity": item.quantity,
                "subtotal": float(subtotal),
            }
        )

    # 4. Generate tracking token
    plain_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(plain_token)

    # 5. Build order payload
    order_payload = {
        "buyer_name": request.buyer_name,
        "notes": request.notes,
        "total_amount": float(total_amount),
        "payment_status": "pending_payment",
        "order_status": "awaiting_payment",
        "tracking_token_hash": token_hash,
        "idempotency_key": idempotency_key,
    }

    # 6. Generate order_number with retry on collision
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
# upload_proof
# ---------------------------------------------------------------------------


async def upload_proof(order_number: str, file: UploadFile, plain_token: str) -> dict:
    """Upload payment proof image for an order."""
    token_hash = _hash_token(plain_token)
    client = get_service_client()

    # 1. Fetch order
    resp = (
        client.table("orders")
        .select("*")
        .eq("order_number", order_number)
        .maybe_single()
        .execute()
    )
    if resp is None or not resp.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}},
        )
    order = resp.data

    # 2. Verify ownership
    if order.get("tracking_token_hash") != token_hash:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "Invalid tracking token"}},
        )

    # 3. Upload guard
    payment_status = order.get("payment_status")
    order_status = order.get("order_status")

    if payment_status in ("paid", "rejected"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "PROOF_UPLOAD_NOT_ALLOWED",
                    "message": "Pembayaran sudah diverifikasi atau ditolak",
                }
            },
        )
    if order_status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "PROOF_UPLOAD_NOT_ALLOWED",
                    "message": "Pesanan sudah dibatalkan",
                }
            },
        )

    # 4. Validate file type
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "File must be JPEG, PNG, or WebP",
                }
            },
        )

    # 5. Read and validate size + magic bytes
    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "File must not exceed 5 MB",
                }
            },
        )
    if not _check_magic(file.content_type, data):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "File content does not match declared type",
                }
            },
        )

    # 6. Upload to storage
    order_id = order["id"]
    ext = _CONTENT_TYPE_TO_EXT[file.content_type]
    path = f"payment-proofs/{order_id}/{uuid4()}.{ext}"
    client.storage.from_("payment-proofs").upload(
        path, data, file_options={"content-type": file.content_type}
    )

    # 7. Update order
    update_resp = (
        client.table("orders")
        .update(
            {
                "payment_proof_path": path,
                "payment_status": "pending_verification",
            }
        )
        .eq("id", order_id)
        .execute()
    )
    return update_resp.data[0]


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
        .select("*")
        .eq("order_id", order["id"])
        .execute()
    )
    order["items"] = items_resp.data or []
    return order
