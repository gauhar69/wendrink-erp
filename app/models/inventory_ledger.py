"""
WENDRINK ERP - Inventory Ledger Model

APPEND-ONLY ledger for all inventory movements.

CRITICAL RULES:
- ❌ NO UPDATE allowed
- ❌ NO DELETE allowed
- ✅ ONLY INSERT allowed
- Stock balance = SUM(change_amount) WHERE ingredient_id = X
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class InventoryEventType(str, Enum):
    """Types of inventory events."""
    
    SUPPLY = "SUPPLY"           # Goods received from supplier
    SALE = "SALE"               # Goods consumed in a sale
    CORRECTION = "CORRECTION"   # Error correction (compensating entry)
    ADJUSTMENT = "ADJUSTMENT"   # Manual adjustment (stocktake)
    WASTE = "WASTE"             # Spoilage / given away free


class InventoryLedger(Base, UUIDMixin, TimestampMixin):
    """
    Inventory Ledger - APPEND-ONLY event log.
    
    This table is the SINGLE SOURCE OF TRUTH for inventory levels.
    Current stock = SUM(change_amount) WHERE ingredient_id = X
    
    ⚠️ NEVER UPDATE OR DELETE ROWS IN THIS TABLE ⚠️
    
    Corrections must be implemented as new CORRECTION events.
    """
    
    __tablename__ = "inventory_ledger"

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="SUPPLY, SALE, CORRECTION, ADJUSTMENT",
    )
    
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Reference to original event for CORRECTION entries",
    )
    
    change_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Positive for incoming, negative for outgoing",
    )
    
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Cost per unit for SUPPLY events",
    )
    
    weighted_average_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        comment="WAC calculated at event time",
    )
    
    cost_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        comment="IMMUTABLE: abs(change_amount) * WAC at event time",
    )
    
    negative_stock: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if this event caused stock to go negative",
    )
    
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Explanation for CORRECTION/ADJUSTMENT events",
    )
    
    business_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Almaty business date (06:00 cutoff)",
    )

    # Relationships
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient",
        back_populates="inventory_entries",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryLedger(ingredient_id={self.ingredient_id}, "
            f"type={self.event_type}, amount={self.change_amount})>"
        )


# Forward references for type hints
from app.models.ingredient import Ingredient  # noqa: E402
