from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class OrderItemDetail(BaseModel):
    menu_type: str
    name: str
    qty: int
    subtotal: Decimal
    menu_id: str | None  # may be null if menu deleted


class OrderListItem(BaseModel):
    order_number: str
    buyer_name: str
    table_number: str
    payment_method: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    item_count: int
    created_at: str


class OrderDetailResponse(BaseModel):
    order_number: str
    buyer_name: str
    table_number: str
    payment_method: str
    notes: str | None
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemDetail]
    cancel_reason: str | None
    created_at: str
    updated_at: str


class RejectRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class CancelRequest(BaseModel):
    reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class HistoryItem(BaseModel):
    order_number: str
    buyer_name: str
    table_number: str
    payment_method: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemDetail]
    cancel_reason: str | None
    created_at: str


class HistoryResponse(BaseModel):
    data: list[HistoryItem]
    total: int
    page: int
    page_size: int
    total_revenue: Decimal
    completed_count: int
    cancelled_count: int
