"""
WENDRINK ERP - Sale Model

Transaction header for sales.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Sale(Base, UUIDMixin, TimestampMixin):
    """
    Sale transaction header.
    
    Contains totals for the entire sale.
    Individual line items are in SaleItem.
    
    Example:
    - Sale #1: 2x Chocolate Milkshake + 1x Iced Latte
    - total_amount: 19,500 KZT (revenue)
    - total_cost: 5,251 KZT (COGS at sale time, IMMUTABLE)
    """
    
    __tablename__ = "sales"

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Total sale amount (revenue) in KZT",
    )
    
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        comment="IMMUTABLE: Total COGS at sale time",
    )
    
    business_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Almaty business date (06:00 cutoff)",
    )

    # Relationships
    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem",
        back_populates="sale",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Sale(id={self.id}, amount={self.total_amount}, date={self.business_date})>"


# Forward references for type hints
from app.models.sale_item import SaleItem  # noqa: E402
