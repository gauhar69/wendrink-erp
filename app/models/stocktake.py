"""
WENDRINK ERP - Stocktake (Inventory Check) Model

Модель для проведения инвентаризации склада.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Date, Numeric, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StocktakeStatus(str, Enum):
    """Статус инвентаризации."""
    DRAFT = "draft"           # Черновик - можно редактировать
    COMPLETED = "completed"   # Завершена - применена к остаткам
    CANCELLED = "cancelled"   # Отменена


class Stocktake(Base):
    """
    Инвентаризация (сверка остатков).
    
    Позволяет:
    - Ввести реальные остатки по каждому ингредиенту
    - Сравнить с системными остатками
    - Выявить расхождения
    - Применить коррекции к ledger
    """
    __tablename__ = "stocktakes"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Дата инвентаризации (бизнес-дата)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Статус
    status: Mapped[str] = mapped_column(
        String(20),
        default=StocktakeStatus.DRAFT.value,
        nullable=False,
    )
    
    # Кто проводил (пока просто текст)
    conducted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Комментарий
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Итоговые суммы (заполняются при завершении)
    total_expected_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )  # Ожидаемая стоимость по системе
    
    total_actual_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )  # Реальная стоимость
    
    total_variance_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )  # Разница (+ излишек, - недостача)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Связь с позициями
    items: Mapped[list["StocktakeItem"]] = relationship(
        "StocktakeItem",
        back_populates="stocktake",
        cascade="all, delete-orphan",
    )


class StocktakeItem(Base):
    """
    Позиция инвентаризации (один ингредиент).
    """
    __tablename__ = "stocktake_items"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Связь с инвентаризацией
    stocktake_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stocktakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Связь с ингредиентом
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False,
    )
    
    # Ожидаемое количество (по системе на момент создания)
    expected_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False
    )
    
    # Реальное количество (вводится при инвентаризации)
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    
    # Разница (actual - expected)
    variance_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    
    # Стоимость единицы (WAC на момент инвентаризации)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    
    # Стоимость расхождения
    variance_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    
    # Комментарий по позиции
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Связи
    stocktake: Mapped["Stocktake"] = relationship(
        "Stocktake", back_populates="items"
    )
    
    ingredient: Mapped["Ingredient"] = relationship("Ingredient")
