from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class MenuCreate(BaseModel):
    name: str
    description: str | None = None
    price: Decimal
    image_url: str | None = None
    is_available: bool = True
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_empty(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be empty")
            return stripped
        return v

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price must be greater than 0")
        return v


class MenuUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    image_url: str | None = None
    is_available: bool | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_empty(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name must not be empty")
            return stripped
        return v

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("price must be greater than 0")
        return v


class AvailabilityUpdate(BaseModel):
    is_available: bool

    model_config = ConfigDict(extra="forbid")


class MenuResponse(BaseModel):
    id: str
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    is_active: bool
    created_at: str
    updated_at: str


class ImageUploadResponse(BaseModel):
    image_url: str
