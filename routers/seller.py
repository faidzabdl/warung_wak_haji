from fastapi import APIRouter, Depends, File, Query, UploadFile

from dependencies.auth import require_seller
from schemas.menu import AvailabilityUpdate, ImageUploadResponse, MenuCreate, MenuResponse, MenuUpdate
from schemas.seller_order import (
    CancelRequest,
    HistoryResponse,
    OrderDetailResponse,
    OrderListItem,
    PaymentRejectRequest,
)
from services.menu_service import (
    create_menu,
    get_all_menus_for_seller,
    set_availability,
    update_menu,
    upload_menu_image,
)
from services.seller_order_service import (
    cancel_order,
    complete_order,
    get_history,
    get_order_detail,
    list_active_orders,
    reject_payment,
    start_processing,
    verify_payment,
)

router = APIRouter(tags=["Seller"])


# NOTE: /upload-image MUST be registered before /{menu_id} to prevent
# "upload-image" being treated as a menu_id path parameter.


@router.post("/seller/menus/upload-image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    _uid: str = Depends(require_seller),
):
    """Upload a menu image and return its public URL. (Seller only)"""
    image_url = await upload_menu_image(file)
    return ImageUploadResponse(image_url=image_url)


@router.post("/seller/menus", response_model=MenuResponse, status_code=201)
async def create_menu_endpoint(
    data: MenuCreate,
    _uid: str = Depends(require_seller),
):
    """Create a new menu item. (Seller only)"""
    return await create_menu(data)


@router.get("/seller/menus", response_model=list[MenuResponse])
async def list_all_menus(
    _uid: str = Depends(require_seller),
):
    """List all menus including inactive/unavailable. (Seller only)"""
    return await get_all_menus_for_seller()


@router.patch("/seller/menus/{menu_id}", response_model=MenuResponse)
async def update_menu_endpoint(
    menu_id: str,
    data: MenuUpdate,
    _uid: str = Depends(require_seller),
):
    """Partially update a menu item. (Seller only)"""
    return await update_menu(menu_id, data)


@router.patch("/seller/menus/{menu_id}/availability", response_model=MenuResponse)
async def set_availability_endpoint(
    menu_id: str,
    data: AvailabilityUpdate,
    _uid: str = Depends(require_seller),
):
    """Toggle menu availability. (Seller only)"""
    return await set_availability(menu_id, data.is_available)


# ---------------------------------------------------------------------------
# Order management
# NOTE: /seller/orders must be registered before /seller/orders/{order_number}
# to prevent "orders" literal being consumed as a path parameter.
# ---------------------------------------------------------------------------


@router.get("/seller/orders", response_model=list[OrderListItem])
async def list_active_orders_endpoint(
    _uid: str = Depends(require_seller),
):
    """List all active orders (awaiting_payment / waiting_processing / processing). (Seller only)"""
    return await list_active_orders()


@router.get("/seller/orders/{order_number}", response_model=OrderDetailResponse)
async def get_order_detail_endpoint(
    order_number: str,
    _uid: str = Depends(require_seller),
):
    """Get order detail including signed payment proof URL. (Seller only)"""
    return await get_order_detail(order_number)


@router.post("/seller/orders/{order_number}/verify-payment")
async def verify_payment_endpoint(
    order_number: str,
    seller_uid: str = Depends(require_seller),
):
    """Confirm payment for an order. (Seller only)"""
    order = await verify_payment(order_number, seller_uid)
    return {"order_number": order["order_number"], "order_status": order["order_status"], "payment_status": order["payment_status"]}


@router.post("/seller/orders/{order_number}/reject-payment")
async def reject_payment_endpoint(
    order_number: str,
    data: PaymentRejectRequest,
    seller_uid: str = Depends(require_seller),
):
    """Reject payment for an order (with reason). (Seller only)"""
    order = await reject_payment(order_number, data.reason, seller_uid)
    return {"order_number": order["order_number"], "order_status": order["order_status"], "payment_status": order["payment_status"]}


@router.post("/seller/orders/{order_number}/start-processing")
async def start_processing_endpoint(
    order_number: str,
    seller_uid: str = Depends(require_seller),
):
    """Advance order to processing state. (Seller only)"""
    order = await start_processing(order_number, seller_uid)
    return {"order_number": order["order_number"], "order_status": order["order_status"]}


@router.post("/seller/orders/{order_number}/complete")
async def complete_order_endpoint(
    order_number: str,
    seller_uid: str = Depends(require_seller),
):
    """Mark an order as completed. (Seller only)"""
    order = await complete_order(order_number, seller_uid)
    return {"order_number": order["order_number"], "order_status": order["order_status"]}


@router.post("/seller/orders/{order_number}/cancel")
async def cancel_order_endpoint(
    order_number: str,
    data: CancelRequest,
    seller_uid: str = Depends(require_seller),
):
    """Cancel an order (with reason). (Seller only)"""
    order = await cancel_order(order_number, data.reason, seller_uid)
    return {"order_number": order["order_number"], "order_status": order["order_status"]}


@router.get("/seller/history", response_model=HistoryResponse)
async def get_history_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    _uid: str = Depends(require_seller),
):
    """Paginated history of completed/cancelled orders with filters. (Seller only)"""
    return await get_history(
        page=page,
        page_size=page_size,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
