from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class OrderItemInput(BaseModel):
    menu_id: str
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v

    model_config = ConfigDict(extra="forbid")


class OrderCreateRequest(BaseModel):
    buyer_name: str
    items: list[OrderItemInput]
    notes: str | None = None

    @field_validator("buyer_name")
    @classmethod
    def buyer_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("buyer_name cannot be empty")
        return v

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("items cannot be empty")
        return v

    model_config = ConfigDict(extra="forbid")


class OrderCreateResponse(BaseModel):
    order_number: str
    tracking_token: str
    total_amount: Decimal
    message: str


class OrderItemSnapshot(BaseModel):
    menu_name: str
    menu_price: Decimal
    quantity: int
    subtotal: Decimal


class OrderTrackResponse(BaseModel):
    order_number: str
    buyer_name: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemSnapshot]
    notes: str | None
    created_at: str
    updated_at: str


class ProofUploadResponse(BaseModel):
    message: str
    payment_status: str
