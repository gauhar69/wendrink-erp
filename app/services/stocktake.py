"""
WENDRINK ERP - Stocktake Service

Сервис для проведения инвентаризации склада.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Ingredient, InventoryLedger
from app.models.stocktake import Stocktake, StocktakeItem, StocktakeStatus
from app.utils.timezone import get_business_date


class StocktakeService:
    """Service for inventory stocktakes."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_stocktake(
        self,
        business_date: Optional[date] = None,
        conducted_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Stocktake:
        """
        Создать новую инвентаризацию.
        
        Автоматически заполняет ожидаемые остатки из системы.
        """
        if business_date is None:
            business_date = get_business_date()
        
        # Создать инвентаризацию
        stocktake = Stocktake(
            business_date=business_date,
            status=StocktakeStatus.DRAFT.value,
            conducted_by=conducted_by,
            notes=notes,
        )
        self.session.add(stocktake)
        await self.session.flush()
        
        # Получить все ингредиенты с остатками
        ingredients_query = select(Ingredient)
        result = await self.session.execute(ingredients_query)
        ingredients = result.scalars().all()
        
        # Для каждого ингредиента создать позицию
        for ingredient in ingredients:
            # Получить текущий остаток
            stock_query = select(func.sum(InventoryLedger.change_amount)).where(
                InventoryLedger.ingredient_id == ingredient.id,
                InventoryLedger.business_date <= business_date,
            )
            stock_result = await self.session.execute(stock_query)
            expected_qty = stock_result.scalar() or Decimal("0")
            
            # Получить текущий WAC
            wac_query = (
                select(InventoryLedger.weighted_average_cost)
                .where(InventoryLedger.ingredient_id == ingredient.id)
                .order_by(InventoryLedger.created_at.desc())
                .limit(1)
            )
            wac_result = await self.session.execute(wac_query)
            unit_cost = wac_result.scalar() or Decimal("0")
            
            item = StocktakeItem(
                stocktake_id=stocktake.id,
                ingredient_id=ingredient.id,
                expected_quantity=expected_qty,
                actual_quantity=None,  # Будет заполнено при инвентаризации
                unit_cost=unit_cost,
            )
            self.session.add(item)
        
        await self.session.flush()
        return stocktake
    
    async def get_stocktake(self, stocktake_id: uuid.UUID) -> Optional[Stocktake]:
        """Получить инвентаризацию по ID."""
        query = (
            select(Stocktake)
            .options(selectinload(Stocktake.items).selectinload(StocktakeItem.ingredient))
            .where(Stocktake.id == stocktake_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_item(
        self,
        stocktake_id: uuid.UUID,
        ingredient_id: uuid.UUID,
        actual_quantity: Decimal,
        notes: Optional[str] = None,
    ) -> StocktakeItem:
        """Обновить реальный остаток для ингредиента."""
        query = (
            select(StocktakeItem)
            .where(
                StocktakeItem.stocktake_id == stocktake_id,
                StocktakeItem.ingredient_id == ingredient_id,
            )
        )
        result = await self.session.execute(query)
        item = result.scalar_one_or_none()
        
        if item is None:
            raise ValueError(f"Item not found for ingredient {ingredient_id}")
        
        # Проверить статус инвентаризации
        stocktake = await self.get_stocktake(stocktake_id)
        if stocktake.status != StocktakeStatus.DRAFT.value:
            raise ValueError("Cannot update completed stocktake")
        
        item.actual_quantity = actual_quantity
        item.variance_quantity = actual_quantity - item.expected_quantity
        item.variance_value = item.variance_quantity * item.unit_cost
        if notes:
            item.notes = notes
        
        await self.session.flush()
        return item
    
    async def update_all_items(
        self,
        stocktake_id: uuid.UUID,
        items: list[dict],
    ) -> Stocktake:
        """
        Обновить все позиции инвентаризации.
        
        items: [{"ingredient_id": "...", "actual_quantity": 1000, "notes": "..."}]
        """
        stocktake = await self.get_stocktake(stocktake_id)
        if stocktake is None:
            raise ValueError(f"Stocktake {stocktake_id} not found")
        
        if stocktake.status != StocktakeStatus.DRAFT.value:
            raise ValueError("Cannot update completed stocktake")
        
        for item_data in items:
            ingredient_id = uuid.UUID(item_data["ingredient_id"])
            actual_qty = Decimal(str(item_data["actual_quantity"]))
            notes = item_data.get("notes")
            
            await self.update_item(
                stocktake_id=stocktake_id,
                ingredient_id=ingredient_id,
                actual_quantity=actual_qty,
                notes=notes,
            )
        
        return await self.get_stocktake(stocktake_id)
    
    async def complete_stocktake(
        self,
        stocktake_id: uuid.UUID,
        apply_adjustments: bool = True,
    ) -> Stocktake:
        """
        Завершить инвентаризацию и применить коррекции.
        
        Args:
            stocktake_id: ID инвентаризации
            apply_adjustments: Создать ADJUSTMENT события в ledger
        """
        stocktake = await self.get_stocktake(stocktake_id)
        if stocktake is None:
            raise ValueError(f"Stocktake {stocktake_id} not found")
        
        if stocktake.status != StocktakeStatus.DRAFT.value:
            raise ValueError("Stocktake already completed")
        
        # Проверить что все позиции заполнены
        for item in stocktake.items:
            if item.actual_quantity is None:
                raise ValueError(
                    f"Actual quantity not set for {item.ingredient.name}"
                )
        
        # Подсчитать итоги
        total_expected = Decimal("0")
        total_actual = Decimal("0")
        total_variance = Decimal("0")
        
        for item in stocktake.items:
            expected_value = item.expected_quantity * item.unit_cost
            actual_value = item.actual_quantity * item.unit_cost
            
            total_expected += expected_value
            total_actual += actual_value
            total_variance += item.variance_value or Decimal("0")
        
        stocktake.total_expected_value = total_expected
        stocktake.total_actual_value = total_actual
        stocktake.total_variance_value = total_variance
        stocktake.status = StocktakeStatus.COMPLETED.value
        stocktake.completed_at = datetime.now(timezone.utc)
        
        # Применить коррекции
        if apply_adjustments:
            await self._apply_adjustments(stocktake)
        
        await self.session.flush()
        return stocktake
    
    async def _apply_adjustments(self, stocktake: Stocktake):
        """Создать ADJUSTMENT события для коррекции остатков."""
        for item in stocktake.items:
            if item.variance_quantity and item.variance_quantity != 0:
                # Создаем ADJUSTMENT событие
                ledger_entry = InventoryLedger(
                    ingredient_id=item.ingredient_id,
                    change_amount=item.variance_quantity,  # + или -
                    event_type="ADJUSTMENT",
                    unit_cost=item.unit_cost,
                    weighted_average_cost=item.unit_cost,
                    cost_snapshot=abs(item.variance_quantity) * item.unit_cost,
                    business_date=stocktake.business_date,
                    reason=f"Инвентаризация {stocktake.business_date}: корректировка",
                    negative_stock=(
                        (item.expected_quantity + item.variance_quantity) < 0
                    ),
                )
                self.session.add(ledger_entry)
    
    async def get_report(self, stocktake_id: uuid.UUID) -> dict:
        """Получить отчёт по инвентаризации."""
        stocktake = await self.get_stocktake(stocktake_id)
        if stocktake is None:
            raise ValueError(f"Stocktake {stocktake_id} not found")
        
        # Группировать позиции
        shortages = []  # Недостачи (actual < expected)
        surpluses = []  # Излишки (actual > expected)
        matches = []    # Совпадение
        
        for item in stocktake.items:
            if item.actual_quantity is None:
                continue
            
            item_data = {
                "ingredient_id": str(item.ingredient_id),
                "ingredient_name": item.ingredient.name,
                "unit": item.ingredient.unit,
                "expected_quantity": str(item.expected_quantity),
                "actual_quantity": str(item.actual_quantity),
                "variance_quantity": str(item.variance_quantity or 0),
                "unit_cost": str(item.unit_cost),
                "variance_value": str(item.variance_value or 0),
                "notes": item.notes,
            }
            
            variance = item.variance_quantity or Decimal("0")
            if variance < -Decimal("0.01"):  # Небольшой допуск
                shortages.append(item_data)
            elif variance > Decimal("0.01"):
                surpluses.append(item_data)
            else:
                matches.append(item_data)
        
        # Сортировать недостачи по сумме (от большей к меньшей)
        shortages.sort(key=lambda x: float(x["variance_value"]))
        surpluses.sort(key=lambda x: float(x["variance_value"]), reverse=True)
        
        return {
            "stocktake_id": str(stocktake.id),
            "business_date": str(stocktake.business_date),
            "status": stocktake.status,
            "conducted_by": stocktake.conducted_by,
            "completed_at": stocktake.completed_at.isoformat() if stocktake.completed_at else None,
            
            "summary": {
                "total_items": len(stocktake.items),
                "shortages_count": len(shortages),
                "surpluses_count": len(surpluses),
                "matches_count": len(matches),
                "total_expected_value": str(stocktake.total_expected_value or 0),
                "total_actual_value": str(stocktake.total_actual_value or 0),
                "total_variance_value": str(stocktake.total_variance_value or 0),
            },
            
            "shortages": shortages,  # Недостачи (убытки)
            "surpluses": surpluses,  # Излишки
            "matches": matches,       # Совпадения
        }
    
    async def list_stocktakes(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Stocktake]:
        """Список инвентаризаций."""
        query = (
            select(Stocktake)
            .options(selectinload(Stocktake.items))
            .order_by(Stocktake.business_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def reset_to_actual(
        self,
        items: list[dict],
        notes: str = "Сброс остатков при запуске системы",
    ) -> Stocktake:
        """
        СПЕЦИАЛЬНАЯ ФУНКЦИЯ: Сброс остатков в ledger.
        
        Используется при первом запуске системы для установки
        РЕАЛЬНЫХ остатков вместо тестовых данных.
        
        items: [{"ingredient_id": "...", "actual_quantity": 1000}]
        """
        business_date = get_business_date()
        
        # Создаём инвентаризацию
        stocktake = await self.create_stocktake(
            business_date=business_date,
            conducted_by="Система",
            notes=notes,
        )
        
        # Обновляем все позиции
        await self.update_all_items(stocktake.id, items)
        
        # Завершаем и применяем
        await self.complete_stocktake(stocktake.id, apply_adjustments=True)
        
        return await self.get_stocktake(stocktake.id)
