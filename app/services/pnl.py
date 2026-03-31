"""
WENDRINK ERP - P&L Service

Profit & Loss calculations.

FORMULA:
    Gross Profit = Revenue - COGS
    Net Profit = Gross Profit - OPEX
    Net Profit = Revenue - COGS - OPEX

LAWS ENFORCED:
- Law 1: Ledger-First (all values from ledger SUM)
- Law 2: Decimal Only
"""

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance_ledger import FinanceLedger
from app.models.sale import Sale
from app.services.finance import FinanceService


@dataclass
class DailyPL:
    """Daily Profit & Loss statement."""
    business_date: date
    
    # Revenue
    revenue: Decimal = Decimal("0")
    transaction_count: int = 0
    
    # COGS
    cogs: Decimal = Decimal("0")
    
    # Gross Profit
    gross_profit: Decimal = Decimal("0")
    gross_margin_percent: Decimal = Decimal("0")
    
    # Waste 
    waste_amount: Decimal = Decimal("0")
    
    # OPEX
    opex_total: Decimal = Decimal("0")
    opex_breakdown: dict[str, Decimal] = field(default_factory=dict)
    
    # Net Profit
    net_profit: Decimal = Decimal("0")
    net_margin_percent: Decimal = Decimal("0")


@dataclass
class MonthlyPL:
    """Monthly Profit & Loss summary."""
    year: int
    month: int
    days_in_month: int
    
    # Totals
    revenue: Decimal = Decimal("0")
    transaction_count: int = 0
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_margin_percent: Decimal = Decimal("0")
    waste_amount: Decimal = Decimal("0")
    opex_total: Decimal = Decimal("0")
    opex_breakdown: dict[str, Decimal] = field(default_factory=dict)
    net_profit: Decimal = Decimal("0")
    net_margin_percent: Decimal = Decimal("0")
    
    # Averages
    avg_daily_revenue: Decimal = Decimal("0")
    avg_daily_cogs: Decimal = Decimal("0")
    avg_daily_opex: Decimal = Decimal("0")
    avg_daily_net_profit: Decimal = Decimal("0")


@dataclass
class PLRangeSummary:
    """P&L summary for a date range."""
    start_date: date
    end_date: date
    days: int
    
    revenue: Decimal = Decimal("0")
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_margin_percent: Decimal = Decimal("0")
    waste_amount: Decimal = Decimal("0")
    opex_total: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    net_margin_percent: Decimal = Decimal("0")


class PLService:
    """
    Service for Profit & Loss calculations.
    
    P&L Formula:
        Gross Profit = Revenue - COGS
        Net Profit = Gross Profit - OPEX
    
    All values are calculated from ledgers, never stored.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.finance_service = FinanceService(session)
    
    # =========================================================================
    # DAILY P&L
    # =========================================================================
    
    async def get_daily_pl(self, business_date: date) -> DailyPL:
        """
        Calculate full P&L for a business date.
        
        Sources:
        - Revenue: SUM(sales.total_amount)
        - COGS: SUM(sales.total_cost)
        - OPEX: SUM(finance_ledger.amount)
        """
        # Get sales data
        sales_result = await self.session.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
                func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
                func.count(Sale.id).label("count"),
            )
            .where(Sale.business_date == business_date)
        )
        sales_row = sales_result.one()
        
        revenue = Decimal(str(sales_row.revenue))
        cogs = Decimal(str(sales_row.cogs))
        transaction_count = sales_row.count
        
        # Get WASTE data
        from app.models.inventory_ledger import InventoryLedger, InventoryEventType
        waste_result = await self.session.execute(
            select(func.coalesce(func.sum(InventoryLedger.cost_snapshot), Decimal("0")))
            .where(InventoryLedger.event_type == InventoryEventType.WASTE.value)
            .where(InventoryLedger.business_date == business_date)
        )
        waste_amount = Decimal(str(waste_result.scalar()))

        # Get OPEX data
        opex = await self.finance_service.get_daily_opex(business_date)
        
        # Calculate profits
        gross_profit = revenue - cogs
        net_profit = gross_profit - waste_amount - opex.total
        
        # Calculate margins (avoid division by zero)
        gross_margin = self._calculate_margin(gross_profit, revenue)
        net_margin = self._calculate_margin(net_profit, revenue)
        
        return DailyPL(
            business_date=business_date,
            revenue=revenue,
            transaction_count=transaction_count,
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_percent=gross_margin,
            waste_amount=waste_amount,
            opex_total=opex.total,
            opex_breakdown=opex.breakdown,
            net_profit=net_profit,
            net_margin_percent=net_margin,
        )
    
    # =========================================================================
    # MONTHLY P&L
    # =========================================================================
    
    async def get_monthly_pl(self, year: int, month: int) -> MonthlyPL:
        """
        Calculate P&L for an entire month.
        """
        start_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        end_date = date(year, month, days_in_month)
        
        # Get sales totals for month
        sales_result = await self.session.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
                func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
                func.count(Sale.id).label("count"),
            )
            .where(Sale.business_date >= start_date)
            .where(Sale.business_date <= end_date)
        )
        sales_row = sales_result.one()
        
        revenue = Decimal(str(sales_row.revenue))
        cogs = Decimal(str(sales_row.cogs))
        transaction_count = sales_row.count
        
        # Get WASTE data
        from app.models.inventory_ledger import InventoryLedger, InventoryEventType
        waste_result = await self.session.execute(
            select(func.coalesce(func.sum(InventoryLedger.cost_snapshot), Decimal("0")))
            .where(InventoryLedger.event_type == InventoryEventType.WASTE.value)
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
        )
        waste_amount = Decimal(str(waste_result.scalar()))

        # Get OPEX totals for month
        opex = await self.finance_service.get_monthly_opex(year, month)
        
        # Calculate profits
        gross_profit = revenue - cogs
        net_profit = gross_profit - waste_amount - opex.total
        
        # Calculate margins
        gross_margin = self._calculate_margin(gross_profit, revenue)
        net_margin = self._calculate_margin(net_profit, revenue)
        
        # Calculate daily averages
        days = Decimal(str(days_in_month))
        
        return MonthlyPL(
            year=year,
            month=month,
            days_in_month=days_in_month,
            revenue=revenue,
            transaction_count=transaction_count,
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_percent=gross_margin,
            waste_amount=waste_amount,
            opex_total=opex.total,
            opex_breakdown=opex.breakdown,
            net_profit=net_profit,
            net_margin_percent=net_margin,
            avg_daily_revenue=revenue / days if days > 0 else Decimal("0"),
            avg_daily_cogs=cogs / days if days > 0 else Decimal("0"),
            avg_daily_opex=opex.total / days if days > 0 else Decimal("0"),
            avg_daily_net_profit=net_profit / days if days > 0 else Decimal("0"),
        )
    
    # =========================================================================
    # DATE RANGE P&L
    # =========================================================================
    
    async def get_pl_range(self, start_date: date, end_date: date) -> PLRangeSummary:
        """
        Calculate P&L for a custom date range.
        """
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")
        
        # Calculate days in range
        days = (end_date - start_date).days + 1
        
        # Get sales totals
        sales_result = await self.session.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
                func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
            )
            .where(Sale.business_date >= start_date)
            .where(Sale.business_date <= end_date)
        )
        sales_row = sales_result.one()
        
        revenue = Decimal(str(sales_row.revenue))
        cogs = Decimal(str(sales_row.cogs))
        
        # Get WASTE totals
        from app.models.inventory_ledger import InventoryLedger, InventoryEventType
        waste_result = await self.session.execute(
            select(func.coalesce(func.sum(InventoryLedger.cost_snapshot), Decimal("0")))
            .where(InventoryLedger.event_type == InventoryEventType.WASTE.value)
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
        )
        waste_amount = Decimal(str(waste_result.scalar()))

        # Get OPEX totals
        opex_result = await self.session.execute(
            select(func.coalesce(func.sum(FinanceLedger.amount), Decimal("0")))
            .where(FinanceLedger.business_date >= start_date)
            .where(FinanceLedger.business_date <= end_date)
        )
        opex_total = Decimal(str(opex_result.scalar()))
        
        # Calculate profits
        gross_profit = revenue - cogs
        net_profit = gross_profit - waste_amount - opex_total
        
        # Calculate margins
        gross_margin = self._calculate_margin(gross_profit, revenue)
        net_margin = self._calculate_margin(net_profit, revenue)
        
        return PLRangeSummary(
            start_date=start_date,
            end_date=end_date,
            days=days,
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_percent=gross_margin,
            waste_amount=waste_amount,
            opex_total=opex_total,
            net_profit=net_profit,
            net_margin_percent=net_margin,
        )
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _calculate_margin(self, profit: Decimal, revenue: Decimal) -> Decimal:
        """
        Calculate profit margin percentage.
        
        Returns 0 if revenue is 0 to avoid division by zero.
        """
        if revenue == Decimal("0"):
            return Decimal("0")
        
        margin = (profit / revenue) * Decimal("100")
        return margin.quantize(Decimal("0.01"))
