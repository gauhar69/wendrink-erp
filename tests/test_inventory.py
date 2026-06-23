import pytest
from decimal import Decimal
import uuid
from datetime import date

from app.models.ingredient import Ingredient
from app.services.inventory import InventoryService


@pytest.mark.asyncio
async def test_first_supply_sets_wac_equal_to_unit_cost(db_session):
    """Test that the first supply of an ingredient sets the WAC equal to the unit cost."""
    service = InventoryService(db_session)
    
    # Create a test ingredient
    ingredient = Ingredient(
        name="Тестовый Ингредиент",
        sku="TEST-ING-1",
        unit="гр",
        package_size=Decimal("1000.0"),
        initial_cost=Decimal("2.5")
    )
    db_session.add(ingredient)
    await db_session.flush()
    
    # Record a supply of 500g for 1500 Tenge (unit cost = 3 Tenge/g)
    entry = await service.record_supply(
        ingredient_id=ingredient.id,
        quantity=Decimal("500.0"),
        total_cost=Decimal("1500.0"),
        business_date=date(2026, 6, 23)
    )
    
    assert entry.unit_cost == Decimal("3.0")
    assert entry.weighted_average_cost == Decimal("3.0")
    
    # Check current stock balance (should be 500)
    balance = await service.get_stock_balance(ingredient.id)
    assert balance == Decimal("500.0")
    
    # Check WAC in ledger is now 3.0
    wac = await service.get_current_wac(ingredient.id)
    assert wac == Decimal("3.0")
    
    # Check that ingredient.current_price has been auto-updated to the unit cost
    await db_session.flush()
    await db_session.refresh(ingredient)
    assert ingredient.current_price == Decimal("3.0")


@pytest.mark.asyncio
async def test_second_supply_calculates_weighted_average_wac(db_session):
    """Test WAC calculation with multiple supplies of different unit costs."""
    service = InventoryService(db_session)
    
    ingredient = Ingredient(
        name="Тестовый Какао",
        sku="TEST-COCOA",
        unit="гр",
        package_size=Decimal("1000.0")
    )
    db_session.add(ingredient)
    await db_session.flush()
    
    # 1. Supply: 100g at 5 Tenge/g (total 500 Tenge)
    await service.record_supply(
        ingredient_id=ingredient.id,
        quantity=Decimal("100.0"),
        total_cost=Decimal("500.0"),
        business_date=date(2026, 6, 23)
    )
    
    # 2. Supply: 100g at 7 Tenge/g (total 700 Tenge)
    # WAC should be (100 * 5 + 100 * 7) / 200 = 6 Tenge/g
    entry = await service.record_supply(
        ingredient_id=ingredient.id,
        quantity=Decimal("100.0"),
        total_cost=Decimal("700.0"),
        business_date=date(2026, 6, 23)
    )
    
    assert entry.weighted_average_cost == Decimal("6.0")
    
    wac = await service.get_current_wac(ingredient.id)
    assert wac == Decimal("6.0")
    
    balance = await service.get_stock_balance(ingredient.id)
    assert balance == Decimal("200.0")


@pytest.mark.asyncio
async def test_supply_with_negative_stock_resets_wac(db_session):
    """Test WAC calculation when current stock is negative."""
    service = InventoryService(db_session)
    
    ingredient = Ingredient(
        name="Тестовое Молоко",
        sku="TEST-MILK",
        unit="мл",
        package_size=Decimal("1000.0")
    )
    db_session.add(ingredient)
    await db_session.flush()
    
    # Force negative stock by deducting balance
    from app.models.inventory_ledger import InventoryLedger, InventoryEventType
    negative_entry = InventoryLedger(
        ingredient_id=ingredient.id,
        event_type=InventoryEventType.SALE.value,
        change_amount=Decimal("-100.0"),
        unit_cost=Decimal("2.0"),
        weighted_average_cost=Decimal("2.0"),
        cost_snapshot=Decimal("200.0"),
        negative_stock=True,
        business_date=date(2026, 6, 23)
    )
    db_session.add(negative_entry)
    await db_session.flush()
    
    # Verify stock balance is indeed negative
    balance = await service.get_stock_balance(ingredient.id)
    assert balance == Decimal("-100.0")
    
    # Record a supply of 500 ml at 3 Tenge/ml (total 1500 Tenge)
    # Since old_stock <= 0, new WAC should simply be the new unit cost (3.0)
    supply_entry = await service.record_supply(
        ingredient_id=ingredient.id,
        quantity=Decimal("500.0"),
        total_cost=Decimal("1500.0"),
        business_date=date(2026, 6, 23)
    )
    
    assert supply_entry.weighted_average_cost == Decimal("3.0")
    
    new_balance = await service.get_stock_balance(ingredient.id)
    assert new_balance == Decimal("400.0")  # -100 + 500 = 400
