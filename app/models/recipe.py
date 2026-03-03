"""
WENDRINK ERP - Recipe Model

Links products to their ingredient requirements.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Recipe(Base, UUIDMixin, TimestampMixin):
    """
    Recipe table - defines ingredient quantities per product.
    
    Example for "Chocolate Milkshake":
    - 0.030 kg cocoa powder
    - 0.200 l fresh milk
    - 0.050 kg ice cream base
    """
    
    __tablename__ = "recipes"
    
    __table_args__ = (
        UniqueConstraint("product_id", "ingredient_id", name="uq_recipe_product_ingredient"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Quantity of ingredient needed per 1 product unit",
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="recipes",
    )
    
    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient",
        back_populates="recipes",
    )

    def __repr__(self) -> str:
        return f"<Recipe(product_id={self.product_id}, ingredient_id={self.ingredient_id}, qty={self.quantity})>"


# Forward references for type hints
from app.models.ingredient import Ingredient  # noqa: E402
from app.models.product import Product  # noqa: E402
