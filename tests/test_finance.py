import pytest
from decimal import Decimal
from datetime import date
import sqlalchemy as sa

from app.models.finance_ledger import FixedCostSetting, FinanceLedger
from app.services.finance import FinanceService


@pytest.mark.asyncio
async def test_fixed_costs_allocation_daily_calculation(db_session):
    """Test that fixed monthly costs are allocated correctly across days in a month."""
    service = FinanceService(db_session)
    
    # Create fixed cost settings
    # 31000 Tenge monthly rent. In Jan (31 days), daily rent should be 1000.00
    rent_setting = FixedCostSetting(
        category_name="Аренда",
        monthly_amount=Decimal("31000.00"),
        is_active=True
    )
    # 30000 Tenge internet. In Jan (31 days), daily should be 30000/31 = 967.74
    internet_setting = FixedCostSetting(
        category_name="Интернет",
        monthly_amount=Decimal("30000.00"),
        is_active=True
    )
    db_session.add_all([rent_setting, internet_setting])
    await db_session.flush()
    
    # Allocate for 2026-01-01
    business_date = date(2026, 1, 1)
    allocated = await service.allocate_daily_fixed_costs(business_date)
    
    assert len(allocated) == 2
    
    # Verify values
    rent_entry = next(e for e in allocated if e.description == "Daily Fixed Cost: Аренда")
    internet_entry = next(e for e in allocated if e.description == "Daily Fixed Cost: Интернет")
    
    assert rent_entry.amount == Decimal("1000.00")
    assert internet_entry.amount == Decimal("967.74")  # 30000 / 31 = 967.7419... -> 967.74


@pytest.mark.asyncio
async def test_fixed_costs_allocation_is_idempotent(db_session):
    """Test that repeated runs of allocation do not create duplicate ledger entries."""
    service = FinanceService(db_session)
    
    rent_setting = FixedCostSetting(
        category_name="Аренда",
        monthly_amount=Decimal("31000.00"),
        is_active=True
    )
    db_session.add(rent_setting)
    await db_session.flush()
    
    business_date = date(2026, 1, 1)
    
    # First run
    allocated1 = await service.allocate_daily_fixed_costs(business_date)
    assert len(allocated1) == 1
    
    # Second run
    allocated2 = await service.allocate_daily_fixed_costs(business_date)
    assert len(allocated2) == 0  # No new allocations
    
    # Verify database has exactly 1 entry
    res = await db_session.execute(sa.select(FinanceLedger))
    entries = res.scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_multiple_settings_same_category_are_both_allocated(db_session):
    """Test that two different settings mapping to the same FinanceCategory are both allocated.
    
    Exposes the bug described in ROADMAP step 2.3.
    """
    service = FinanceService(db_session)
    
    # Both "Коммунальные" and "Электричество" map to UTILITIES category code
    comm_setting = FixedCostSetting(
        category_name="Коммунальные",
        monthly_amount=Decimal("31000.00"),
        is_active=True
    )
    elec_setting = FixedCostSetting(
        category_name="Электричество",
        monthly_amount=Decimal("62000.00"),
        is_active=True
    )
    db_session.add_all([comm_setting, elec_setting])
    await db_session.flush()
    
    business_date = date(2026, 1, 1)
    allocated = await service.allocate_daily_fixed_costs(business_date)
    
    # Expecting BOTH to be allocated (2 entries)
    # If the bug is active, only the first one is created and len(allocated) == 1.
    assert len(allocated) == 2


@pytest.mark.asyncio
async def test_adding_new_setting_after_allocation_is_still_allocated(db_session):
    """Test that if we add a new setting that maps to the same category after a prior allocation,
    the new setting is allocated correctly on the next run.
    """
    service = FinanceService(db_session)
    business_date = date(2026, 1, 1)
    
    # 1. Create first setting mapping to UTILITIES
    comm_setting = FixedCostSetting(
        category_name="Коммунальные",
        monthly_amount=Decimal("31000.00"),
        is_active=True
    )
    db_session.add(comm_setting)
    await db_session.flush()
    
    # Allocate once
    allocated1 = await service.allocate_daily_fixed_costs(business_date)
    assert len(allocated1) == 1
    
    # Flush changes to database simulating separate transaction/run
    await db_session.flush()
    
    # 2. Now add second setting mapping to UTILITIES
    elec_setting = FixedCostSetting(
        category_name="Электричество",
        monthly_amount=Decimal("62000.00"),
        is_active=True
    )
    db_session.add(elec_setting)
    await db_session.flush()
    
    # Allocate again. Elec setting should be allocated.
    allocated2 = await service.allocate_daily_fixed_costs(business_date)
    
    # If the bug is active, it sees UTILITIES category exists and skips "Электричество".
    # If fixed, it allocates "Электричество" successfully.
    assert len(allocated2) == 1
    assert allocated2[0].description == "Daily Fixed Cost: Электричество"

