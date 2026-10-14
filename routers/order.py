from decimal import Decimal

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from dependencies.rate_limit import limiter
from schemas.order import OrderCreateRequest, OrderCreateResponse, OrderItemSnapshot, OrderTrackResponse
from services import order_service

router = APIRouter(tags=["Orders"])


@router.post("/orders", status_code=201)
@limiter.limit("20/minute")
async def create_order(
    request: Request,
    body: OrderCreateRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Create a new order. Returns tracking_token shown ONCE only."""
    result, plain_token, is_duplicate = await order_service.create_order(body, idempotency_key)

    if is_duplicate:
        return JSONResponse(
            status_code=200,
            content={
                "order_number": result["order_number"],
                "message": "Pesanan sudah ada (idempotency key dikenali).",
                "total_amount": str(result["total_amount"]),
            },
        )

    response = OrderCreateResponse(
        order_number=result["order_number"],
        tracking_token=plain_token,
        total_amount=Decimal(str(result["total_amount"])),
        message="Simpan token ini. Tidak dapat ditampilkan ulang.",
    )
    return JSONResponse(status_code=201, content=response.model_dump(mode="json"))


@router.get("/orders/track/{tracking_token}", status_code=200)
@limiter.limit("30/minute")
async def track_order(request: Request, tracking_token: str):
    """Track order status by tracking token."""
    result = await order_service.track_order(tracking_token)
    items = [
        OrderItemSnapshot(
            menu_name=item["menu_name_snapshot"],
            menu_price=Decimal(str(item["menu_price_snapshot"])),
            menu_type=item.get("menu_type", "Makanan"),
            quantity=item["quantity"],
            subtotal=Decimal(str(item["subtotal"])),
        )
        for item in result.get("items", [])
    ]
    response = OrderTrackResponse(
        order_number=result["order_number"],
        buyer_name=result["buyer_name"],
        table_number=result["table_number"],
        payment_method=result["payment_method"],
        order_status=result["order_status"],
        payment_status=result["payment_status"],
        total_amount=Decimal(str(result["total_amount"])),
        items=items,
        notes=result.get("notes"),
        created_at=str(result["created_at"]),
        updated_at=str(result["updated_at"]),
    )
    return response
