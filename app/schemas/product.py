"""
WENDRINK ERP - Product Schemas

Pydantic schemas for product validation and serialization.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, ConfigDict

from app.schemas.base import BaseSchema


class ProductCreate(BaseSchema):
    """Schema for creating a new product."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Product name",
        examples=["Chocolate Milkshake", "Iced Latte"],
    )
    
    price: Decimal = Field(
        ...,
        gt=Decimal("0"),
        decimal_places=2,
        description="Selling price in KZT",
        examples=[Decimal("2000.00"), Decimal("1500.50")],
    )
    
    is_active: bool = Field(
        True,
        description="Whether product is available for sale",
    )
    
    @field_validator("price", mode="before")
    @classmethod
    def coerce_price_to_decimal(cls, v: str | float | Decimal) -> Decimal:
        """Convert price to Decimal, rejecting floats at runtime."""
        if isinstance(v, float):
            # Accept but convert - JSON doesn't have Decimal type
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class ProductUpdate(BaseSchema):
    """Schema for updating a product."""
    
    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New product name",
    )
    
    price: Decimal | None = Field(
        None,
        gt=Decimal("0"),
        description="New selling price in KZT",
    )
    
    is_active: bool | None = Field(
        None,
        description="New availability status",
    )
    
    @field_validator("price", mode="before")
    @classmethod
    def coerce_price_to_decimal(cls, v: str | float | Decimal | None) -> Decimal | None:
        """Convert price to Decimal if provided."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class ProductRead(BaseSchema):
    """Schema for reading a product."""
    
    model_config = ConfigDict(strict=False)
    
    id: UUID
    name: str
    price: Decimal  # Serialized as string via BaseSchema
    is_active: bool
    created_at: datetime
    pos_code: int | None = None
    category: str | None = None
    sku: str | None = None
    
    @field_validator("pos_code", mode="before")
    @classmethod
    def coerce_pos_code(cls, v: int | Decimal | None) -> int | None:
        """Convert Decimal from DB to int."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return int(v)
        return v
