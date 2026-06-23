import pytest
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal

from app.utils.timezone import get_business_date
from app.services.pnl import PLService
from app.models.sale import Sale
from app.models.finance_ledger import FinanceLedger


def test_business_date_timezone_boundaries():
    """Test business date boundaries (Law 4: Cutoff 06:00 Almaty)."""
    # Almaty is UTC+5. 
    
    # Example 1: 2026-06-23 01:30:00 UTC -> Almaty: 2026-06-23 06:30:00 (after 06:00)
    # Business date: 2026-06-23
    dt1 = datetime(2026, 6, 23, 1, 30, 0, tzinfo=timezone.utc)
    assert get_business_date(dt1) == date(2026, 6, 23)
    
    # Example 2: 2026-06-23 00:30:00 UTC -> Almaty: 2026-06-23 05:30:00 (before 06:00)
    # Business date: 2026-06-22 (yesterday)
    dt2 = datetime(2026, 6, 23, 0, 30, 0, tzinfo=timezone.utc)
    assert get_business_date(dt2) == date(2026, 6, 22)
    
    # Example 3: 2026-06-23 23:30:00 UTC -> Almaty: 2026-06-24 04:30:00 (before 06:00 next day)
    # Business date: 2026-06-23
    dt3 = datetime(2026, 6, 23, 23, 30, 0, tzinfo=timezone.utc)
    assert get_business_date(dt3) == date(2026, 6, 23)


@pytest.mark.asyncio
async def test_calculate_daily_pnl_correctly(db_session):
    """Test full P&L formula: Net Profit = Revenue - COGS - OPEX."""
    pnl_service = PLService(db_session)
    business_date = date(2026, 6, 23)
    
    # 1. Add some sales
    # Sale 1: Revenue = 3000, COGS = 1000
    sale1 = Sale(
        total_amount=Decimal("3000.00"),
        total_cost=Decimal("1000.00"),
        business_date=business_date
    )
    # Sale 2: Revenue = 2000, COGS = 800
    sale2 = Sale(
        total_amount=Decimal("2000.00"),
        total_cost=Decimal("800.00"),
        business_date=business_date
    )
    db_session.add_all([sale1, sale2])
    
    # 2. Add some daily OPEX in finance_ledger
    # Rent daily: 1500
    rent = FinanceLedger(
        category="RENT",
        amount=Decimal("1500.00"),
        business_date=business_date,
        description="Daily Rent"
    )
    # Salary daily: 2000
    salary = FinanceLedger(
        category="SALARY",
        amount=Decimal("2000.00"),
        business_date=business_date,
        description="Daily Salary"
    )
    db_session.add_all([rent, salary])
    await db_session.flush()
    
    # 3. Calculate P&L
    # Revenue = 5000, COGS = 1800, OPEX = 3500
    # Gross Profit = 5000 - 1800 = 3200 (Margin = 3200 / 5000 * 100 = 64.00%)
    # Net Profit = 3200 - 3500 = -300 (Margin = -300 / 5000 * 100 = -6.00%)
    statement = await pnl_service.get_daily_pl(business_date)
    
    assert statement.revenue == Decimal("5000.00")
    assert statement.cogs == Decimal("1800.00")
    assert statement.gross_profit == Decimal("3200.00")
    assert statement.gross_margin_percent == Decimal("64.00")
    assert statement.opex_total == Decimal("3500.00")
    assert statement.net_profit == Decimal("-300.00")
    assert statement.net_margin_percent == Decimal("-6.00")
    assert statement.transaction_count == 2


@pytest.mark.asyncio
async def test_pnl_margin_handles_zero_revenue_safely(db_session):
    """Test that get_daily_pl doesn't crash with DivisionByZero if there are no sales."""
    pnl_service = PLService(db_session)
    business_date = date(2026, 6, 23)
    
    # No sales, only OPEX
    salary = FinanceLedger(
        category="SALARY",
        amount=Decimal("2000.00"),
        business_date=business_date,
        description="Daily Salary"
    )
    db_session.add(salary)
    await db_session.flush()
    
    statement = await pnl_service.get_daily_pl(business_date)
    
    assert statement.revenue == Decimal("0")
    assert statement.cogs == Decimal("0")
    assert statement.gross_profit == Decimal("0")
    assert statement.gross_margin_percent == Decimal("0")
    assert statement.net_profit == Decimal("-2000.00")
    assert statement.net_margin_percent == Decimal("0")
    assert statement.transaction_count == 0
