import re
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


_TABLE_NUMBER_RE = re.compile(r"^[1-8]$")


class OrderCreateRequest(BaseModel):
    buyer_name: str
    table_number: str
    payment_method: str
    items: list[OrderItemInput]
    notes: str | None = None

    @field_validator("buyer_name")
    @classmethod
    def buyer_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("buyer_name cannot be empty")
        return v

    @field_validator("table_number")
    @classmethod
    def table_number_valid(cls, v: str) -> str:
        v = v.strip()
        if not _TABLE_NUMBER_RE.match(v):
            raise ValueError("table_number must be a number between 1 and 8")
        return v

    @field_validator("payment_method")
    @classmethod
    def payment_method_valid(cls, v: str) -> str:
        if v not in ("qris", "cash"):
            raise ValueError("payment_method must be 'qris' or 'cash'")
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
    menu_type: str
    quantity: int
    subtotal: Decimal


class OrderTrackResponse(BaseModel):
    order_number: str
    buyer_name: str
    table_number: str
    payment_method: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    items: list[OrderItemSnapshot]
    notes: str | None
    created_at: str
    updated_at: str
