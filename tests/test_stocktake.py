import pytest
from decimal import Decimal
from datetime import date, datetime, timezone
import uuid

from app.models.stocktake import Stocktake, StocktakeItem, StocktakeStatus
from app.models.ingredient import Ingredient
from app.services.stocktake import StocktakeService


@pytest.mark.asyncio
async def test_stocktake_complete_atomic_prevent_double_clicks(db_session):
    """Test that a stocktake can only be completed once.
    
    Verifies PATCH-010 fix.
    """
    service = StocktakeService(db_session)
    
    # 1. Create a test ingredient
    milk = Ingredient(
        name="Молоко",
        sku="ING-MILK",
        unit="мл",
        package_size=Decimal("1000.0")
    )
    db_session.add(milk)
    await db_session.flush()
    
    # 2. Create a stocktake draft
    stocktake = Stocktake(
        status=StocktakeStatus.DRAFT.value,
        business_date=date(2026, 6, 23),
        conducted_by="Тестер"
    )
    db_session.add(stocktake)
    await db_session.flush()
    
    # Add a stocktake item with actual quantity set
    item = StocktakeItem(
        stocktake_id=stocktake.id,
        ingredient_id=milk.id,
        expected_quantity=Decimal("500.0"),
        actual_quantity=Decimal("450.0"),  # 50ml shortage
        unit_cost=Decimal("2.0")
    )
    db_session.add(item)
    await db_session.flush()
    
    # 3. First completion - should succeed
    completed = await service.complete_stocktake(stocktake.id, apply_adjustments=True)
    assert completed.status == StocktakeStatus.COMPLETED.value
    assert completed.completed_at is not None
    assert completed.adjustments_applied_at is not None
    
    # 4. Second completion - should raise ValueError (already completed)
    with pytest.raises(ValueError) as excinfo:
        await service.complete_stocktake(stocktake.id, apply_adjustments=True)
        
    assert "already completed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_stocktake_reapply_idempotency_marker(db_session):
    """Test that complete_stocktake sets adjustments_applied_at, indicating adjustments are applied."""
    service = StocktakeService(db_session)
    
    milk = Ingredient(
        name="Молоко",
        sku="ING-MILK",
        unit="мл",
        package_size=Decimal("1000.0")
    )
    db_session.add(milk)
    await db_session.flush()
    
    stocktake = Stocktake(
        status=StocktakeStatus.DRAFT.value,
        business_date=date(2026, 6, 23),
        conducted_by="Тестер"
    )
    db_session.add(stocktake)
    await db_session.flush()
    
    item = StocktakeItem(
        stocktake_id=stocktake.id,
        ingredient_id=milk.id,
        expected_quantity=Decimal("500.0"),
        actual_quantity=Decimal("500.0"),
        unit_cost=Decimal("2.0")
    )
    db_session.add(item)
    await db_session.flush()
    
    # Complete stocktake
    completed = await service.complete_stocktake(stocktake.id, apply_adjustments=True)
    assert completed.adjustments_applied_at is not None
    
    # Verify adjustments_applied_at is set in the DB
    await db_session.refresh(completed)
    assert completed.adjustments_applied_at is not None
