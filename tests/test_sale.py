import pytest
import asyncio
from decimal import Decimal
from datetime import date

from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe import Recipe
from app.services.sale import SaleService, SaleItemInput
from app.services.inventory import InventoryService


@pytest.mark.asyncio
async def test_sale_captures_correct_cogs_snapshot(db_session):
    """Test that a sale records correct COGS based on current WAC and fixes it in ledger."""
    inventory_service = InventoryService(db_session)
    sale_service = SaleService(db_session)
    
    # 1. Create a test ingredient
    cocoa = Ingredient(
        name="Порошок Какао",
        sku="ING-COCOA",
        unit="гр",
        package_size=Decimal("1000.0")
    )
    db_session.add(cocoa)
    await db_session.flush()
    
    # 2. Add supply to establish WAC = 5.0
    await inventory_service.record_supply(
        ingredient_id=cocoa.id,
        quantity=Decimal("100.0"),
        total_cost=Decimal("500.0"),
        business_date=date(2026, 6, 23)
    )
    
    # 3. Create a Product
    ice_cream = Product(
        name="Какао Мороженое",
        price=Decimal("150.0"),
        sku="P-ICECREAM"
    )
    db_session.add(ice_cream)
    await db_session.flush()
    
    # 4. Create a Recipe (requires 10g cocoa)
    recipe = Recipe(
        product_id=ice_cream.id,
        ingredient_id=cocoa.id,
        quantity=Decimal("10.0")
    )
    db_session.add(recipe)
    await db_session.flush()
    
    # 5. Create a sale of 2 items (requires 20g cocoa)
    # Expected COGS: 20 * WAC(5.0) = 100.0 Tenge. Expected Revenue: 2 * 150 = 300.0
    result = await sale_service.create_sale(
        items=[SaleItemInput(product_id=ice_cream.id, quantity=2)],
        business_date=date(2026, 6, 23)
    )
    
    assert result.sale.total_amount == Decimal("300.0")
    assert result.sale.total_cost == Decimal("100.0")
    assert len(result.negative_stock_warnings) == 0
    
    # Check ledger entry
    from app.models.inventory_ledger import InventoryLedger, InventoryEventType
    import sqlalchemy as sa
    res = await db_session.execute(
        sa.select(InventoryLedger).where(
            InventoryLedger.event_type == InventoryEventType.SALE.value
        )
    )
    ledger_entries = res.scalars().all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].change_amount == Decimal("-20.0")
    assert ledger_entries[0].cost_snapshot == Decimal("100.0")
    assert ledger_entries[0].weighted_average_cost == Decimal("5.0")
    assert ledger_entries[0].negative_stock is False


@pytest.mark.asyncio
async def test_subsequent_supply_does_not_affect_past_cogs_snapshot(db_session):
    """Test that historical sale cost_snapshot remains immutable when new supplies arrive."""
    inventory_service = InventoryService(db_session)
    sale_service = SaleService(db_session)
    
    cocoa = Ingredient(
        name="Порошок Какао",
        sku="ING-COCOA",
        unit="гр",
        package_size=Decimal("1000.0")
    )
    db_session.add(cocoa)
    await db_session.flush()
    
    # Supply 1: WAC = 5.0
    await inventory_service.record_supply(
        ingredient_id=cocoa.id,
        quantity=Decimal("100.0"),
        total_cost=Decimal("500.0"),
        business_date=date(2026, 6, 23)
    )
    await asyncio.sleep(0.02)
    
    ice_cream = Product(
        name="Какао Мороженое",
        price=Decimal("150.0"),
        sku="P-ICECREAM"
    )
    db_session.add(ice_cream)
    await db_session.flush()
    
    recipe = Recipe(
        product_id=ice_cream.id,
        ingredient_id=cocoa.id,
        quantity=Decimal("10.0")
    )
    db_session.add(recipe)
    await db_session.flush()
    
    # Sale 1: COGS = 10g * 5.0 = 50.0 Tenge
    sale_res1 = await sale_service.create_sale(
        items=[SaleItemInput(product_id=ice_cream.id, quantity=1)],
        business_date=date(2026, 6, 23)
    )
    assert sale_res1.sale.total_cost == Decimal("50.0")
    await asyncio.sleep(0.02)
    
    # Supply 2: 90g at 15.0 Tenge/g (total 1350 Tenge)
    # Remaining stock = 90g. New WAC = (90 * 5.0 + 90 * 15.0) / 180 = 10.0 Tenge/g
    await inventory_service.record_supply(
        ingredient_id=cocoa.id,
        quantity=Decimal("90.0"),
        total_cost=Decimal("1350.0"),
        business_date=date(2026, 6, 23)
    )
    await asyncio.sleep(0.02)
    
    # Verify current WAC is now 10.0
    import sqlalchemy as sa
    from app.models.inventory_ledger import InventoryLedger
    res = await db_session.execute(sa.select(InventoryLedger).order_by(InventoryLedger.created_at.asc()))
    for e in res.scalars().all():
        print(f"DEBUG LEDGER: id={e.id} type={e.event_type} qty={e.change_amount} wac={e.weighted_average_cost} created_at={e.created_at}")
        
    wac = await inventory_service.get_current_wac(cocoa.id)
    assert wac == Decimal("10.0")
    
    # Sale 2: COGS = 10g * 10.0 = 100.0 Tenge
    sale_res2 = await sale_service.create_sale(
        items=[SaleItemInput(product_id=ice_cream.id, quantity=1)],
        business_date=date(2026, 6, 23)
    )
    assert sale_res2.sale.total_cost == Decimal("100.0")
    
    # Check that Sale 1's cost in database has NOT changed and is still 50.0
    await db_session.refresh(sale_res1.sale)
    assert sale_res1.sale.total_cost == Decimal("50.0")


@pytest.mark.asyncio
async def test_sale_with_negative_stock_allowed_but_flagged(db_session):
    """Test that a sale with insufficient stock is allowed but sets negative stock warning."""
    inventory_service = InventoryService(db_session)
    sale_service = SaleService(db_session)
    
    milk = Ingredient(
        name="Молоко",
        sku="ING-MILK",
        unit="мл",
        package_size=Decimal("1000.0"),
        initial_cost=Decimal("1.5")  # Initial WAC fallback
    )
    db_session.add(milk)
    await db_session.flush()
    
    # No supply has been recorded, stock is 0.
    cappuccino = Product(
        name="Капучино",
        price=Decimal("400.0"),
        sku="P-CAPPUCCINO"
    )
    db_session.add(cappuccino)
    await db_session.flush()
    
    recipe = Recipe(
        product_id=cappuccino.id,
        ingredient_id=milk.id,
        quantity=Decimal("150.0")
    )
    db_session.add(recipe)
    await db_session.flush()
    
    # Create sale of 1 cappuccino (requires 150ml milk, which is out of stock)
    # Expected: sale allowed, warning generated, ledger negative_stock = True
    result = await sale_service.create_sale(
        items=[SaleItemInput(product_id=cappuccino.id, quantity=1)],
        business_date=date(2026, 6, 23)
    )
    
    assert result.sale.total_amount == Decimal("400.0")
    assert result.sale.total_cost == Decimal("225.0")  # 150 * 1.5 (initial_cost fallback)
    assert len(result.negative_stock_warnings) == 1
    assert "Negative stock" in result.negative_stock_warnings[0]
    
    # Verify stock balance is now negative
    balance = await inventory_service.get_stock_balance(milk.id)
    assert balance == Decimal("-150.0")
    
    # Verify ledger entry negative_stock is True
    from app.models.inventory_ledger import InventoryLedger, InventoryEventType
    import sqlalchemy as sa
    res = await db_session.execute(
        sa.select(InventoryLedger).where(
            InventoryLedger.event_type == InventoryEventType.SALE.value
        )
    )
    ledger_entries = res.scalars().all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].negative_stock is True
