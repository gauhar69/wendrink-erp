"""
WENDRINK ERP - Recipe Schemas

Pydantic schemas for recipe validation and serialization.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class RecipeCreate(BaseSchema):
    """Schema for creating a recipe entry."""
    
    product_id: UUID = Field(
        ...,
        description="Product this recipe belongs to",
    )
    
    ingredient_id: UUID = Field(
        ...,
        description="Ingredient used in this recipe",
    )
    
    quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Quantity of ingredient per product unit",
        examples=[Decimal("0.030"), Decimal("0.200")],
    )
    
    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_quantity_to_decimal(cls, v: str | float | Decimal) -> Decimal:
        """Convert quantity to Decimal."""
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class RecipeRead(BaseSchema):
    """Schema for reading a recipe entry."""
    
    id: UUID
    product_id: UUID
    ingredient_id: UUID
    quantity: Decimal  # Serialized as string
    created_at: datetime
