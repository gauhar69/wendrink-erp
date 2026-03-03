"""
WENDRINK ERP - Inventory Schemas

Pydantic schemas for inventory ledger validation and serialization.

CRITICAL: These schemas enforce Law 1 (Ledger-First) and Law 2 (Decimal Only).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


# Event types allowed for different operations
SupplyEventType = Literal["SUPPLY"]
SaleEventType = Literal["SALE"]
CorrectionEventType = Literal["CORRECTION"]
AdjustmentEventType = Literal["ADJUSTMENT"]


class InventoryEventCreate(BaseSchema):
    """
    Base schema for creating inventory events.
    
    This is a generic schema - specific operations may use specialized schemas.
    """
    
    ingredient_id: UUID = Field(
        ...,
        description="Ingredient this event affects",
    )
    
    event_type: Literal["SUPPLY", "SALE", "CORRECTION", "ADJUSTMENT"] = Field(
        ...,
        description="Type of inventory event",
    )
    
    event_id: UUID | None = Field(
        None,
        description="Reference to original event (required for CORRECTION)",
    )
    
    change_amount: Decimal = Field(
        ...,
        description="Change in quantity (positive=in, negative=out)",
    )
    
    unit_cost: Decimal | None = Field(
        None,
        description="Cost per unit (required for SUPPLY events)",
    )
    
    reason: str | None = Field(
        None,
        max_length=500,
        description="Explanation (recommended for CORRECTION/ADJUSTMENT)",
    )
    
    @field_validator("change_amount", "unit_cost", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v: str | float | Decimal | None) -> Decimal | None:
        """Convert numeric values to Decimal."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v
    
    @field_validator("event_id")
    @classmethod
    def validate_correction_has_event_id(cls, v: UUID | None, info) -> UUID | None:
        """CORRECTION events must reference original event."""
        # Note: This validation needs access to event_type
        # Full validation done at service layer
        return v


class InventoryLedgerRead(BaseSchema):
    """Schema for reading inventory ledger entries."""
    
    id: UUID
    ingredient_id: UUID
    event_type: str
    event_id: UUID | None
    change_amount: Decimal
    unit_cost: Decimal | None
    weighted_average_cost: Decimal
    cost_snapshot: Decimal
    negative_stock: bool
    reason: str | None
    business_date: date
    created_at: datetime


class InventoryBalanceRead(BaseSchema):
    """Schema for reading current inventory balance."""
    
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    current_balance: Decimal  # SUM(change_amount)
    weighted_average_cost: Decimal
    total_value: Decimal  # balance * WAC


# ============================================================================
# Bulk Supply Schemas (Invoice Import)
# ============================================================================

class BulkSupplyItemRequest(BaseSchema):
    """
    Single item in a bulk supply invoice.
    
    Supports lookup by EITHER ingredient_id OR ingredient_name (not both).
    If both provided, ingredient_id takes priority.
    """
    
    ingredient_id: UUID | None = Field(
        None,
        description="Ingredient UUID (preferred for API integrations)"
    )
    
    ingredient_name: str | None = Field(
        None,
        max_length=100,
        description="Exact ingredient name (for manual entry)"
    )
    
    quantity_packs: Decimal = Field(
        ...,
        gt=0,
        description="Number of packages/boxes (e.g., 4 for '4 коробки')"
    )
    
    price_per_pack: Decimal = Field(
        ...,
        gt=0,
        description="Price per single package in KZT (e.g., 56000)"
    )
    
    @field_validator("quantity_packs", "price_per_pack", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v):
        """Convert to Decimal for financial precision."""
        if v is None:
            return v
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class BulkSupplyRequest(BaseSchema):
    """
    Complete supply invoice with multiple items.
    
    All items are processed in a single atomic transaction.
    If any item fails validation, the entire invoice is rejected.
    """
    
    business_date: date = Field(
        ...,
        description="Invoice date (Almaty business date)"
    )
    
    supplier_note: str | None = Field(
        None,
        max_length=500,
        description="Invoice number or supplier notes"
    )
    
    items: list[BulkSupplyItemRequest] = Field(
        ...,
        min_length=1,
        description="List of supply items (at least 1)"
    )
    
    total_expected: Decimal = Field(
        ...,
        gt=0,
        description="Expected invoice total for verification (must match sum of items)"
    )
    
    @field_validator("total_expected", mode="before")
    @classmethod
    def coerce_total_to_decimal(cls, v):
        """Convert to Decimal."""
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v)
        return v


class BulkSupplyItemResponse(BaseSchema):
    """Result for a single supply item after processing."""
    
    ingredient_id: str
    ingredient_name: str
    quantity_packs: str
    quantity_base_units: str  # In grams/ml
    price_per_pack: str
    line_total: str  # quantity_packs × price_per_pack
    unit_cost: str  # price_per_pack / package_size
    new_wac: str  # New Weighted Average Cost after this supply


class BulkSupplyResponse(BaseSchema):
    """Response after processing a bulk supply invoice."""
    
    status: str = "success"
    business_date: str
    supplier_note: str | None
    items_count: int
    total_calculated: str  # Sum of all line totals
    total_expected: str  # Expected total from request (for verification)
    items: list[BulkSupplyItemResponse]
    ledger_ids: list[str]  # IDs of created ledger entries

