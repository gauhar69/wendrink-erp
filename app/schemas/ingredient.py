"""
WENDRINK ERP - Ingredient Schemas

Pydantic schemas for ingredient validation and serialization.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class IngredientCreate(BaseSchema):
    """Schema for creating a new ingredient."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Ingredient name",
        examples=["Cocoa powder", "Fresh milk"],
    )
    
    sku: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stock Keeping Unit (unique identifier)",
        examples=["ICE-POWDER-001", "MILK-FRESH-001"],
    )
    
    unit: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unit of measurement: kg, l, pcs, g, ml",
        examples=["g", "ml", "pcs"],
    )
    
    package_size: Decimal = Field(
        default=Decimal("1.0"),
        gt=0,
        description="Number of base units per package (e.g., 24000 for '3KG * 8 packs')",
        examples=["24000", "1000", "1"],
    )
    
    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        """Validate unit is one of allowed values."""
        allowed = {"kg", "l", "pcs", "g", "ml"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"Unit must be one of: {', '.join(sorted(allowed))}")
        return v_lower
    
    @field_validator("package_size", mode="before")
    @classmethod
    def coerce_package_size(cls, v):
        """Convert to Decimal."""
        if v is None:
            return Decimal("1.0")
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class IngredientUpdate(BaseSchema):
    """Schema for updating an ingredient."""
    
    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New ingredient name",
    )
    
    unit: str | None = Field(
        None,
        min_length=1,
        max_length=20,
        description="New unit of measurement",
    )
    
    package_size: Decimal | None = Field(
        None,
        gt=0,
        description="New package size in base units",
    )

    current_price: Decimal | None = Field(
        None,
        ge=0,
        description="Текущая цена за единицу (г/мл/шт). Используется для расчёта себестоимости.",
    )

    norm_stock: Decimal | None = Field(
        None,
        ge=0,
        description="Нормативный запас в коробках (или базовых единицах)",
    )

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str | None) -> str | None:
        """Validate unit is one of allowed values."""
        if v is None:
            return v
        allowed = {"kg", "l", "pcs", "g", "ml"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"Unit must be one of: {', '.join(sorted(allowed))}")
        return v_lower
    
    @field_validator("package_size", "current_price", "norm_stock", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v):
        """Convert float/int/str → Decimal (needed for strict mode)."""
        if v is None:
            return v
        if isinstance(v, (float, int)):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class IngredientRead(BaseSchema):
    """Schema for reading an ingredient."""
    
    id: UUID
    name: str
    sku: str
    unit: str
    package_size: Decimal = Field(
        description="Base units per package (e.g., 24000 grams for '3KG*8')"
    )
    position_number: int | None = None
    norm_stock: Decimal | None = None
    initial_cost: Decimal | None = None
    current_price: Decimal | None = None
    category: str | None = None
    created_at: datetime
