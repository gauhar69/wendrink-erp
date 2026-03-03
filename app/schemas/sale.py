"""
WENDRINK ERP - Sale Schemas

Pydantic schemas for sales validation and serialization.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class SaleItemCreate(BaseSchema):
    """Schema for creating a sale line item."""
    
    product_id: UUID = Field(
        ...,
        description="Product being sold",
    )
    
    quantity: int = Field(
        ...,
        gt=0,
        description="Number of units sold",
        examples=[1, 2, 5],
    )


class SaleCreate(BaseSchema):
    """Schema for creating a sale."""
    
    items: list[SaleItemCreate] = Field(
        ...,
        min_length=1,
        description="Line items in this sale",
    )
    
    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list[SaleItemCreate]) -> list[SaleItemCreate]:
        """Ensure at least one item in sale."""
        if not v:
            raise ValueError("Sale must have at least one item")
        return v


class SaleItemRead(BaseSchema):
    """Schema for reading a sale line item."""
    
    id: UUID
    sale_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal  # IMMUTABLE price at sale time
    line_total: Decimal
    created_at: datetime


class SaleRead(BaseSchema):
    """Schema for reading a sale."""
    
    id: UUID
    total_amount: Decimal  # Revenue
    total_cost: Decimal    # COGS (IMMUTABLE)
    business_date: date
    created_at: datetime
    items: list[SaleItemRead] = Field(default_factory=list)
    
    # Computed fields for convenience
    @property
    def gross_profit(self) -> Decimal:
        """Calculate gross profit (revenue - COGS)."""
        return self.total_amount - self.total_cost
    
    @property
    def gross_margin_percent(self) -> Decimal:
        """Calculate gross margin percentage."""
        if self.total_amount == Decimal("0"):
            return Decimal("0")
        return (self.gross_profit / self.total_amount) * Decimal("100")


class DailySalesSummary(BaseSchema):
    """Schema for daily sales summary."""
    
    business_date: date
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal
    transaction_count: int
