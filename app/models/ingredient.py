"""
WENDRINK ERP - Ingredient Model
"""
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Ingredient(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ingredients"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    
    # Package size - количество базовых единиц (гр/мл) в одной коробке
    # Пример: "3КГ * 8 пакетов" = 24000 гр
    # Для штучных товаров (ложки, стаканы) = 1.0

    # Cost tracking
    initial_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    # current_price — текущая цена за единицу (г/мл/шт).
    # Устанавливается вручную в разделе "Цены сырья".
    # Приоритет расчёта себестоимости: current_price > WAC из ledger > initial_cost
    # Numeric(14,8): 8 знаков — 56000/24000=2.33333333×24000=55999.9992→56000 ✓
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    package_size: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("1.0"),
        server_default="1.0",
    )

    # Norm stock (НЗ) - нормативный запас для автозаявок
    norm_stock: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    position_number: Mapped[int | None] = mapped_column(nullable=True)
    
    recipes: Mapped[list["Recipe"]] = relationship("Recipe", back_populates="ingredient", lazy="selectin")
    inventory_entries: Mapped[list["InventoryLedger"]] = relationship("InventoryLedger", back_populates="ingredient", lazy="noload")
    
    def __repr__(self) -> str:
        return f"<Ingredient(name='{self.name}', sku='{self.sku}', package_size={self.package_size})>"


from app.models.inventory_ledger import InventoryLedger
from app.models.recipe import Recipe

