from decimal import Decimal

from fastapi import APIRouter, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from dependencies.rate_limit import limiter
from schemas.order import OrderCreateRequest, OrderCreateResponse, OrderItemSnapshot, OrderTrackResponse, ProofUploadResponse
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


@router.post("/orders/{order_number}/proof", status_code=200)
@limiter.limit("10/minute")
async def upload_proof(
    request: Request,
    order_number: str,
    file: UploadFile = File(...),
    x_tracking_token: str = Header(..., alias="X-Tracking-Token"),
):
    """Upload payment proof image. Requires X-Tracking-Token header."""
    result = await order_service.upload_proof(order_number, file, x_tracking_token)
    response = ProofUploadResponse(
        message="Bukti pembayaran berhasil diunggah.",
        payment_status=result["payment_status"],
    )
    return response


@router.get("/orders/track/{tracking_token}", status_code=200)
@limiter.limit("30/minute")
async def track_order(request: Request, tracking_token: str):
    """Track order status by tracking token."""
    result = await order_service.track_order(tracking_token)
    items = [
        OrderItemSnapshot(
            menu_name=item["menu_name_snapshot"],
            menu_price=Decimal(str(item["menu_price_snapshot"])),
            quantity=item["quantity"],
            subtotal=Decimal(str(item["subtotal"])),
        )
        for item in result.get("items", [])
    ]
    response = OrderTrackResponse(
        order_number=result["order_number"],
        buyer_name=result["buyer_name"],
        order_status=result["order_status"],
        payment_status=result["payment_status"],
        total_amount=Decimal(str(result["total_amount"])),
        items=items,
        notes=result.get("notes"),
        created_at=str(result["created_at"]),
        updated_at=str(result["updated_at"]),
    )
    return response
