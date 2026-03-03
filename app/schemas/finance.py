"""
WENDRINK ERP - Finance Schemas

Pydantic schemas for finance ledger validation and serialization.

CRITICAL: These schemas enforce Law 1 (Ledger-First) and Law 9 (OPEX Allocation).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


# Finance categories
FinanceCategoryType = Literal[
    "SALARY",
    "RENT",
    "UTILITIES",
    "SECURITY",
    "INTERNET",
    "EQUIPMENT",
    "SUPPLIES",
    "MARKETING",
    "OTHER",
]


class FinanceCreate(BaseSchema):
    """Schema for creating a finance ledger entry."""
    
    category: FinanceCategoryType = Field(
        ...,
        description="Expense category",
    )
    
    amount: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Expense amount in KZT",
        examples=[Decimal("24387.09"), Decimal("9677.42")],
    )
    
    description: str | None = Field(
        None,
        max_length=500,
        description="Additional details about the expense",
    )
    
    business_date: date = Field(
        ...,
        description="Business date for this expense allocation",
    )
    
    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount_to_decimal(cls, v: str | float | Decimal) -> Decimal:
        """Convert amount to Decimal."""
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class FinanceRead(BaseSchema):
    """Schema for reading a finance ledger entry."""
    
    id: UUID
    category: str
    amount: Decimal
    description: str | None
    business_date: date
    created_at: datetime


class DailyOPEXRead(BaseSchema):
    """Schema for daily OPEX summary."""
    
    business_date: date
    total_opex: Decimal
    breakdown: dict[str, Decimal]  # category → amount


# =========================================================================
# FIXED COST SETTINGS SCHEMAS
# =========================================================================

class FixedCostSettingCreate(BaseSchema):
    """Schema for creating/updating a fixed cost setting."""
    
    category_name: str = Field(..., min_length=1, max_length=100)
    monthly_amount: Decimal = Field(..., ge=Decimal("0"))
    is_active: bool = True
    description: str | None = None

    @field_validator("monthly_amount", mode="before")
    @classmethod
    def coerce_amount_to_decimal(cls, v: str | float | Decimal) -> Decimal:
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class FixedCostSettingRead(BaseSchema):
    """Schema for reading a fixed cost setting."""
    
    id: UUID
    category_name: str
    monthly_amount: Decimal
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime
