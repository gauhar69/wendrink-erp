"""
WENDRINK ERP - Product Model
"""
from decimal import Decimal
from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name_kk: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pos_code: Mapped[int | None] = mapped_column(Numeric(10, 0), unique=True, nullable=True, index=True)
    
    serving_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    serving_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    
    recipes: Mapped[list["Recipe"]] = relationship("Recipe", back_populates="product", lazy="selectin")
    sale_items: Mapped[list["SaleItem"]] = relationship("SaleItem", back_populates="product", lazy="noload")
    
    def __repr__(self) -> str:
        return f"<Product(name='{self.name}', sku='{self.sku}')>"

from app.models.recipe import Recipe
from app.models.sale_item import SaleItem
