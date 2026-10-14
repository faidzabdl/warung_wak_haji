import logging
from decimal import Decimal

from fastapi import HTTPException

from db import get_service_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active / history order statuses
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = ("awaiting_payment", "waiting_processing", "processing", "ready")
_HISTORY_STATUSES = ("completed", "cancelled")


# ---------------------------------------------------------------------------
# Transition guard
# ---------------------------------------------------------------------------


def _assert_transition(order: dict, action: str) -> None:
    """Raise HTTPException(409, INVALID_STATUS_TRANSITION) if the current
    order state does not allow *action*."""
    order_status = order["order_status"]
    payment_method = order.get("payment_method", "qris")

    if action == "verify_payment":
        if payment_method != "qris":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "verify-payment only applies to QRIS orders",
                    }
                },
            )
        if order_status != "awaiting_payment":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Cannot verify payment: order status is not awaiting_payment",
                    }
                },
            )

    elif action == "reject_payment":
        if payment_method != "qris":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "reject-payment only applies to QRIS orders",
                    }
                },
            )
        if order_status != "awaiting_payment":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Cannot reject payment: order status is not awaiting_payment",
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
                        "message": "Cannot start processing: order status is not waiting_processing",
                    }
                },
            )

    elif action == "mark_ready":
        if order_status != "processing":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Cannot mark ready: order status is not processing",
                    }
                },
            )

    elif action == "complete":
        if order_status != "ready":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": "Cannot complete order: order status is not ready",
                    }
                },
            )

    elif action == "cancel":
        if order_status not in ("awaiting_payment", "waiting_processing"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "INVALID_STATUS_TRANSITION",
                        "message": (
                            "Pesanan hanya bisa dibatalkan saat menunggu pembayaran "
                            "atau menunggu diproses"
                        ),
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
        .select("menu_id, menu_name_snapshot, menu_type, quantity, subtotal")
        .eq("order_id", order_id)
        .execute()
    )
    return result.data or []


def _normalize_items(raw_items: list[dict]) -> list[dict]:
    """Map DB column names to schema field names."""
    return [
        {
            "menu_type": item.get("menu_type", "Makanan"),
            "name": item["menu_name_snapshot"],
            "qty": item["quantity"],
            "subtotal": item["subtotal"],
            "menu_id": item.get("menu_id"),
        }
        for item in raw_items
    ]


def _atomic_update(
    service_client,
    order_id: str,
    expected_status: str,
    update_payload: dict,
) -> dict:
    """Update order atomically: only succeeds if order_status == expected_status.

    - 0 rows updated → fetch current order to distinguish 404 vs 409.
    - Order not found → 404.
    - Order found but status mismatch → 409 with current status in message.
    Returns the updated order row.
    """
    result = (
        service_client.table("orders")
        .update(update_payload)
        .eq("id", order_id)
        .eq("order_status", expected_status)
        .execute()
    )
    if not result.data:
        # Distinguish: order gone vs status already changed
        check = (
            service_client.table("orders")
            .select("order_status")
            .eq("id", order_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}},
            )
        current_status = check.data["order_status"]
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": (
                        f"Status order saat ini adalah '{current_status}', "
                        f"bukan '{expected_status}'. Muat ulang dan coba lagi."
                    ),
                }
            },
        )
    return result.data[0]


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def list_active_orders() -> list[dict]:
    """Return orders with status in _ACTIVE_STATUSES, ordered by created_at ASC."""
    service_client = get_service_client()

    result = (
        service_client.table("orders")
        .select(
            "order_number, buyer_name, table_number, payment_method, "
            "order_status, payment_status, total_amount, created_at, id"
        )
        .in_("order_status", list(_ACTIVE_STATUSES))
        .order("created_at", desc=False)
        .execute()
    )
    orders = result.data or []

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
                "table_number": order["table_number"],
                "payment_method": order["payment_method"],
                "order_status": order["order_status"],
                "payment_status": order["payment_status"],
                "total_amount": order["total_amount"],
                "item_count": item_count,
                "created_at": str(order["created_at"]),
            }
        )
    return enriched


async def get_order_detail(order_number: str) -> dict:
    """Fetch order + items."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)

    raw_items = _fetch_order_items(service_client, order["id"])
    items = _normalize_items(raw_items)

    return {
        "order_number": order["order_number"],
        "buyer_name": order["buyer_name"],
        "table_number": order["table_number"],
        "payment_method": order["payment_method"],
        "notes": order.get("notes"),
        "order_status": order["order_status"],
        "payment_status": order["payment_status"],
        "total_amount": order["total_amount"],
        "items": items,
        "cancel_reason": order.get("cancel_reason"),
        "created_at": str(order["created_at"]),
        "updated_at": str(order["updated_at"]),
    }


async def verify_payment(order_number: str, seller_uid: str) -> dict:
    """Verify QRIS payment: awaiting_payment → processing, payment_status → paid."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "verify_payment")

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status="awaiting_payment",
        update_payload={"payment_status": "paid", "order_status": "processing"},
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="payment_verified",
        actor=seller_uid,
        metadata={"previous_order_status": "awaiting_payment"},
    )

    return updated


async def reject_payment(order_number: str, reason: str | None, seller_uid: str) -> dict:
    """Reject QRIS payment: awaiting_payment → cancelled, payment_status → rejected."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "reject_payment")

    update_payload: dict = {
        "payment_status": "rejected",
        "order_status": "cancelled",
    }
    if reason:
        update_payload["cancel_reason"] = reason

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status="awaiting_payment",
        update_payload=update_payload,
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="payment_rejected",
        actor=seller_uid,
        metadata={"reason": reason or ""},
    )

    return updated


async def start_processing(order_number: str, seller_uid: str) -> dict:
    """Advance order from waiting_processing → processing."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "start_processing")

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status="waiting_processing",
        update_payload={"order_status": "processing"},
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="processing_started",
        actor=seller_uid,
        metadata={},
    )

    return updated


async def mark_ready(order_number: str, seller_uid: str) -> dict:
    """Advance order from processing → ready."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "mark_ready")

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status="processing",
        update_payload={"order_status": "ready"},
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="order_ready",
        actor=seller_uid,
        metadata={},
    )

    return updated


async def complete_order(order_number: str, seller_uid: str) -> dict:
    """Advance order from ready → completed.

    If payment_method='cash', also sets payment_status='paid' atomically.
    """
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "complete")

    update_payload: dict = {"order_status": "completed"}
    if order.get("payment_method") == "cash":
        update_payload["payment_status"] = "paid"

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status="ready",
        update_payload=update_payload,
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="order_completed",
        actor=seller_uid,
        metadata={"payment_method": order.get("payment_method", "")},
    )

    return updated


async def cancel_order(order_number: str, reason: str | None, seller_uid: str) -> dict:
    """Cancel an order from awaiting_payment or waiting_processing only."""
    service_client = get_service_client()
    order = _fetch_order_by_number(service_client, order_number)
    _assert_transition(order, "cancel")

    update_payload: dict = {"order_status": "cancelled"}
    if reason:
        update_payload["cancel_reason"] = reason

    updated = _atomic_update(
        service_client,
        order["id"],
        expected_status=order["order_status"],  # either awaiting_payment or waiting_processing
        update_payload=update_payload,
    )

    _write_audit_log(
        service_client,
        order["id"],
        action="order_cancelled",
        actor=seller_uid,
        metadata={"reason": reason or "", "previous_order_status": order["order_status"]},
    )

    return updated


async def get_history(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Return paginated history (completed/cancelled orders) with summary stats."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    service_client = get_service_client()

    if status and status in _HISTORY_STATUSES:
        status_filter = [status]
    else:
        status_filter = list(_HISTORY_STATUSES)

    # Paginated query
    query = (
        service_client.table("orders")
        .select(
            "id, order_number, buyer_name, table_number, payment_method, "
            "order_status, payment_status, total_amount, cancel_reason, created_at",
            count="exact",
        )
        .in_("order_status", status_filter)
        .order("created_at", desc=True)
    )

    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59")

    query = query.range(offset, offset + page_size - 1)
    result = query.execute()

    orders = result.data or []
    total = result.count if result.count is not None else 0

    # Summary stats via DB-side GROUP BY aggregation.
    # PostgREST supports aggregate columns in select when using group-by hint.
    # We call a raw Supabase RPC or use two targeted COUNT/SUM queries to avoid
    # pulling all rows to Python (PostgREST default page cap is 1000 rows).
    completed_resp = (
        service_client.table("orders")
        .select("total_amount")
        .eq("order_status", "completed")
        .execute()
    )
    cancelled_resp = (
        service_client.table("orders")
        .select("id", count="exact")
        .eq("order_status", "cancelled")
        .execute()
    )
    total_revenue = Decimal("0")
    for row in (completed_resp.data or []):
        total_revenue += Decimal(str(row.get("total_amount") or 0))
    completed_count = len(completed_resp.data or [])
    cancelled_count = cancelled_resp.count if cancelled_resp.count is not None else 0

    # Enrich each order with its items
    data = []
    for order in orders:
        raw_items = _fetch_order_items(service_client, order["id"])
        items = _normalize_items(raw_items)
        data.append(
            {
                "order_number": order["order_number"],
                "buyer_name": order["buyer_name"],
                "table_number": order["table_number"],
                "payment_method": order["payment_method"],
                "order_status": order["order_status"],
                "payment_status": order["payment_status"],
                "total_amount": order["total_amount"],
                "items": items,
                "cancel_reason": order.get("cancel_reason"),
                "created_at": str(order["created_at"]),
            }
        )

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_revenue": total_revenue,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
    }
