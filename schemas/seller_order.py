from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class OrderItemDetail(BaseModel):
    menu_name: str
    menu_price: Decimal
    quantity: int
    subtotal: Decimal
    menu_id: str | None  # may be null if menu deleted


class OrderListItem(BaseModel):
    order_number: str
    buyer_name: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    item_count: int
    created_at: str


class OrderDetailResponse(BaseModel):
    order_number: str
    buyer_name: str
    notes: str | None
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemDetail]
    payment_proof_url: str | None  # signed URL, 1-hour expiry; None if not uploaded
    cancel_reason: str | None
    reject_reason: str | None
    created_at: str
    updated_at: str


class PaymentRejectRequest(BaseModel):
    reason: str  # required, non-empty
    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must not be empty")
        return v


class CancelRequest(BaseModel):
    reason: str  # required, non-empty
    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must not be empty")
        return v


class HistoryItem(BaseModel):
    order_number: str
    buyer_name: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemDetail]
    cancel_reason: str | None
    reject_reason: str | None
    created_at: str


class HistoryResponse(BaseModel):
    data: list[HistoryItem]
    total: int
    page: int
    page_size: int
