"""
WENDRINK ERP - Sale Item Model

Line items for sales transactions.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SaleItem(Base, UUIDMixin, TimestampMixin):
    """
    Sale line item.
    
    Captures product details at the moment of sale.
    Price is snapshotted and IMMUTABLE.
    
    Example:
    - 2x Chocolate Milkshake @ 2,000 KZT = 4,000 KZT
    """
    
    __tablename__ = "sale_items"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of units sold",
    )
    
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="IMMUTABLE: Price per unit at sale time",
    )
    
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="quantity * unit_price",
    )
    
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Captured COGS (total cost of ingredients) for this item",
    )

    # Relationships
    sale: Mapped["Sale"] = relationship(
        "Sale",
        back_populates="items",
    )
    
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="sale_items",
    )

    def __repr__(self) -> str:
        return f"<SaleItem(product_id={self.product_id}, qty={self.quantity}, total={self.line_total})>"


# Forward references for type hints
from app.models.product import Product  # noqa: E402
from app.models.sale import Sale  # noqa: E402
