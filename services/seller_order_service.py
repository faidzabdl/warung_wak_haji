import logging

from fastapi import HTTPException

from db import get_service_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active order statuses
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = ("awaiting_payment", "waiting_processing", "processing")
_HISTORY_STATUSES = ("completed", "cancelled")


# ---------------------------------------------------------------------------
# Transition guard
# ---------------------------------------------------------------------------


def _assert_transition(order: dict, action: str) -> None:
    """Raise HTTPException(409, INVALID_STATUS_TRANSITION) if the current
    order state does not allow *action*."""
    order_status = order["order_status"]
    payment_status = order["payment_status"]

    if action == "verify_payment":
        if payment_status != "pending_verification":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            "Cannot verify payment: payment status is not pending_verification"
                        ),
                    }
                },
            )
        if order_status != "awaiting_payment":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            "Cannot verify payment: order status is not awaiting_payment"
                        ),
                    }
                },
            )

    elif action == "reject_payment":
        if payment_status != "pending_verification":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            "Cannot reject payment: payment status is not pending_verification"
                        ),
                    }
                },
            )

    elif action == "start_processing":
        if order_status != "waiting_processing":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            "Cannot start processing: order status is not waiting_processing"
                        ),
                    }
                },
            )

    elif action == "complete":
        if order_status != "processing":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Cannot complete order: order status is not processing",
                    }
                },
            )

    elif action == "cancel":
        if order_status in ("completed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Pesanan sudah selesai atau dibatalkan",
                    }
                },
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_audit_log(
    service_client,
    order_id: str,
    action: str,
    actor: str,
    metadata: dict,
) -> None:
    """Insert a row into audit_logs (best-effort, errors are logged not raised)."""
    try:
        service_client.table("audit_logs").insert(
            {
                "order_id": order_id,
                "action": action,
                "actor": actor,
                "metadata": metadata,
            }
        ).execute()
    except Exception as exc:  # pragma: no cover
        logger.warning("audit_log write failed for order %s action %s: %s", order_id, action, exc)


def _fetch_order_by_number(service_client, order_number: str) -> dict:
    """Fetch a single order by order_number; raise 404 if not found."""
    result = (
        service_client.table("orders")
        .select("*")
        .eq("order_number", order_number)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}},
        )
    return result.data


def _fetch_order_items(service_client, order_id: str) -> list[dict]:
    """Fetch all items for the given order_id."""
    result = (
        service_client.table("order_items")
        .select("menu_id, menu_name_snapshot, menu_price_snapshot, quantity, subtotal")
        .eq("order_id", order_id)
        .execute()
    )
    return result.data or []


def _normalize_items(raw_items: list[dict]) -> list[dict]:
    """Map DB column names to schema field names."""
    return [
        {
            "menu_name": item["menu_name_snapshot"],
            "menu_price": item["menu_price_snapshot"],
            "quantity": item["quantity"],
            "subtotal": item["subtotal"],
            "menu_id": item.get("menu_id"),
        }
        for item in raw_items
    ]


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def list_active_orders() -> list[dict]:
    """Return orders with status in (awaiting_payment, waiting_processing, processing),
    ordered by created_at ASC, each including item_count."""
    service_client = get_service_client()

    result = (
        service_client.table("orders")
        .select("order_number, buyer_name, order_status, payment_status, total_amount, created_at, id")
        .in_("order_status", list(_ACTIVE_STATUSES))
        .order("created_at", desc=False)
        .execute()
    )
    orders = result.data or []

    # Attach item_count for each order
    enriched = []
    for order in orders:
        items_result = (
            service_client.table("order_items")
            .select("id", count="exact")
            .eq("order_id", order["id"])
            .execute()
        )
        item_count = items_result.count if items_result.count is not None else 0
        enriched.append(
            {
                "order_number": order["order_number"],
                "buyer_name": order["buyer_name"],
                "order_status": order["order_status"],
                "payment_status": order["payment_status"],
                "total_amount": order["total_amount"],
                "item_count": item_count,
                "created_at": str(order["created_at"]),
            }
        )
    return enriched


async def get_order_detail(order_number: str) -> dict:
    """Fetch order + items; generate signed URL for payment_proof_path if present."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)

    raw_items = _fetch_order_items(service_client, order["id"])
    items = _normalize_items(raw_items)

    # Generate signed URL for payment proof
    payment_proof_url: str | None = None
    proof_path: str | None = order.get("payment_proof_path")
    if proof_path:
        try:
            signed = service_client.storage.from_("payment-proofs").create_signed_url(
                proof_path, expires_in=3600
            )
            payment_proof_url = signed.get("signedURL") or signed.get("signedUrl")
        except Exception as exc:
            logger.warning("Failed to generate signed URL for %s: %s", proof_path, exc)
            payment_proof_url = None

    return {
        "order_number": order["order_number"],
        "buyer_name": order["buyer_name"],
        "notes": order.get("notes"),
        "order_status": order["order_status"],
        "payment_status": order["payment_status"],
        "total_amount": order["total_amount"],
        "items": items,
        "payment_proof_url": payment_proof_url,
        "cancel_reason": order.get("cancel_reason"),
        "reject_reason": order.get("reject_reason"),
        "created_at": str(order["created_at"]),
        "updated_at": str(order["updated_at"]),
    }


async def verify_payment(order_number: str, seller_uid: str) -> dict:
    """Verify payment: pending_verification → paid, awaiting_payment → waiting_processing."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "verify_payment")

    service_client.table("orders").update(
        {"payment_status": "paid", "order_status": "waiting_processing"}
    ).eq("id", order["id"]).execute()

    _write_audit_log(
        service_client,
        order["id"],
        action="payment_verified",
        actor=seller_uid,
        metadata={"previous_payment_status": "pending_verification"},
    )

    order.update({"payment_status": "paid", "order_status": "waiting_processing"})
    return order


async def reject_payment(order_number: str, reason: str, seller_uid: str) -> dict:
    """Reject payment: pending_verification → rejected, order → cancelled."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "reject_payment")

    service_client.table("orders").update(
        {
            "payment_status": "rejected",
            "order_status": "cancelled",
            "reject_reason": reason,
        }
    ).eq("id", order["id"]).execute()

    _write_audit_log(
        service_client,
        order["id"],
        action="payment_rejected",
        actor=seller_uid,
        metadata={"reason": reason},
    )

    order.update(
        {"payment_status": "rejected", "order_status": "cancelled", "reject_reason": reason}
    )
    return order


async def start_processing(order_number: str, seller_uid: str) -> dict:
    """Advance order from waiting_processing → processing."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "start_processing")

    service_client.table("orders").update(
        {"order_status": "processing"}
    ).eq("id", order["id"]).execute()

    _write_audit_log(
        service_client,
        order["id"],
        action="processing_started",
        actor=seller_uid,
        metadata={},
    )

    order["order_status"] = "processing"
    return order


async def complete_order(order_number: str, seller_uid: str) -> dict:
    """Advance order from processing → completed."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "complete")

    service_client.table("orders").update(
        {"order_status": "completed"}
    ).eq("id", order["id"]).execute()

    _write_audit_log(
        service_client,
        order["id"],
        action="order_completed",
        actor=seller_uid,
        metadata={},
    )

    order["order_status"] = "completed"
    return order


async def cancel_order(order_number: str, reason: str, seller_uid: str) -> dict:
    """Cancel an order from any non-terminal state."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "cancel")

    service_client.table("orders").update(
        {"order_status": "cancelled", "cancel_reason": reason}
    ).eq("id", order["id"]).execute()

    _write_audit_log(
        service_client,
        order["id"],
        action="order_cancelled",
        actor=seller_uid,
        metadata={"reason": reason},
    )

    order.update({"order_status": "cancelled", "cancel_reason": reason})
    return order


async def get_history(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Return paginated history (completed/cancelled orders) with optional filters."""
    # Clamp pagination params
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    service_client = get_service_client()

    # Determine the status filter set
    if status and status in _HISTORY_STATUSES:
        status_filter = [status]
    else:
        status_filter = list(_HISTORY_STATUSES)

    query = (
        service_client.table("orders")
        .select(
            "id, order_number, buyer_name, order_status, payment_status, total_amount, "
            "cancel_reason, reject_reason, created_at",
            count="exact",
        )
        .in_("order_status", status_filter)
        .order("created_at", desc=True)
    )

    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        # Include the full end day by appending end-of-day time
        query = query.lte("created_at", f"{date_to}T23:59:59")

    query = query.range(offset, offset + page_size - 1)
    result = query.execute()

    orders = result.data or []
    total = result.count if result.count is not None else 0

    # Enrich each order with its items
    data = []
    for order in orders:
        raw_items = _fetch_order_items(service_client, order["id"])
        items = _normalize_items(raw_items)
        data.append(
            {
                "order_number": order["order_number"],
                "buyer_name": order["buyer_name"],
                "order_status": order["order_status"],
                "payment_status": order["payment_status"],
                "total_amount": order["total_amount"],
                "items": items,
                "cancel_reason": order.get("cancel_reason"),
                "reject_reason": order.get("reject_reason"),
                "created_at": str(order["created_at"]),
            }
        )

    return {"data": data, "total": total, "page": page, "page_size": page_size}
