"""
WENDRINK ERP - Finance Service

Handles operational expense (OPEX) operations.

LAWS ENFORCED:
- Law 1: Ledger-First (OPEX = SUM of finance_ledger)
- Law 2: Decimal Only
- Law 9: OPEX Allocation Across Daily Periods
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance_ledger import FinanceCategory, FinanceLedger, FixedCostSetting


@dataclass
class DailyOPEX:
    """Daily OPEX breakdown."""
    business_date: date
    total: Decimal
    breakdown: dict[str, Decimal]


@dataclass 
class MonthlyOPEX:
    """Monthly OPEX summary."""
    year: int
    month: int
    days_in_month: int
    total: Decimal
    breakdown: dict[str, Decimal]
    daily_average: Decimal


class FinanceService:
    """
    Service for finance/OPEX operations.
    
    OPEX is tracked via append-only finance_ledger.
    All calculations use Decimal for financial accuracy.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # OPEX QUERIES
    # =========================================================================
    
    async def get_daily_opex(self, business_date: date) -> DailyOPEX:
        """
        Get total OPEX and breakdown for a business date.
        
        OPEX = SUM(finance_ledger.amount) for the date.
        """
        # Get breakdown by category
        result = await self.session.execute(
            select(
                FinanceLedger.category,
                func.sum(FinanceLedger.amount).label("total")
            )
            .where(FinanceLedger.business_date == business_date)
            .group_by(FinanceLedger.category)
        )
        rows = result.all()
        
        breakdown: dict[str, Decimal] = {}
        total = Decimal("0")
        
        for row in rows:
            amount = Decimal(str(row.total))
            breakdown[row.category] = amount
            total += amount
        
        return DailyOPEX(
            business_date=business_date,
            total=total,
            breakdown=breakdown,
        )
    
    async def get_monthly_opex(self, year: int, month: int) -> MonthlyOPEX:
        """
        Get total OPEX for a month with breakdown.
        """
        start_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        end_date = date(year, month, days_in_month)
        
        # Get breakdown by category
        result = await self.session.execute(
            select(
                FinanceLedger.category,
                func.sum(FinanceLedger.amount).label("total")
            )
            .where(FinanceLedger.business_date >= start_date)
            .where(FinanceLedger.business_date <= end_date)
            .group_by(FinanceLedger.category)
        )
        rows = result.all()
        
        breakdown: dict[str, Decimal] = {}
        total = Decimal("0")
        
        for row in rows:
            amount = Decimal(str(row.total))
            breakdown[row.category] = amount
            total += amount
        
        daily_average = total / Decimal(str(days_in_month)) if days_in_month > 0 else Decimal("0")
        
        return MonthlyOPEX(
            year=year,
            month=month,
            days_in_month=days_in_month,
            total=total,
            breakdown=breakdown,
            daily_average=daily_average,
        )
    
    # =========================================================================
    # OPEX CREATION
    # =========================================================================
    
    async def create_entry(
        self,
        category: str,
        amount: Decimal,
        business_date: date,
        description: str | None = None,
    ) -> FinanceLedger:
        """
        Create a single finance ledger entry.
        
        Args:
            category: OPEX category (must be valid FinanceCategory)
            amount: Daily amount
            business_date: Allocation date
            description: Optional description
            
        Returns:
            Created entry
        """
        # Validate category
        valid_categories = [c.value for c in FinanceCategory]
        if category not in valid_categories:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {valid_categories}")
        
        if amount < Decimal("0"):
            raise ValueError("Amount cannot be negative")
        
        entry = FinanceLedger(
            category=category,
            amount=amount,
            business_date=business_date,
            description=description,
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry
    
    # =========================================================================
    # MONTHLY ALLOCATION (Law 9)
    # =========================================================================
    
    async def allocate_monthly_opex(
        self,
        category: str,
        monthly_amount: Decimal,
        year: int,
        month: int,
        description: str | None = None,
        skip_existing: bool = True,
    ) -> list[FinanceLedger]:
        """
        Distribute monthly expense evenly across all days in the month.
        
        Formula:
            daily_amount = monthly_amount / days_in_month
            
        Example:
            756,000 KZT / 31 days = 24,387.10 KZT/day
            
        Args:
            category: OPEX category
            monthly_amount: Total monthly expense
            year: Target year
            month: Target month
            description: Optional description
            skip_existing: If True, skip days that already have entries
            
        Returns:
            List of created entries
        """
        # Validate category
        valid_categories = [c.value for c in FinanceCategory]
        if category not in valid_categories:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {valid_categories}")
        
        if monthly_amount < Decimal("0"):
            raise ValueError("Monthly amount cannot be negative")
        
        days_in_month = monthrange(year, month)[1]
        
        # Calculate daily amount (rounded to 2 decimal places)
        daily_amount = (monthly_amount / Decimal(str(days_in_month))).quantize(Decimal("0.01"))
        
        entries = []
        
        for day in range(1, days_in_month + 1):
            business_date = date(year, month, day)
            
            # Check for existing entry if skip_existing is True
            if skip_existing:
                existing = await self.session.execute(
                    select(FinanceLedger)
                    .where(FinanceLedger.category == category)
                    .where(FinanceLedger.business_date == business_date)
                )
                if existing.scalar_one_or_none() is not None:
                    continue
            
            entry = FinanceLedger(
                category=category,
                amount=daily_amount,
                business_date=business_date,
                description=description or f"Monthly allocation for {year}-{month:02d}",
            )
            
            self.session.add(entry)
            entries.append(entry)
        
        await self.session.flush()
        
        return entries
    
    async def check_month_exists(
        self,
        year: int,
        month: int,
    ) -> dict[str, int]:
        """
        Check if OPEX entries exist for a month.
        
        Returns:
            Dict of category -> entry count
        """
        start_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        end_date = date(year, month, days_in_month)
        
        result = await self.session.execute(
            select(
                FinanceLedger.category,
                func.count(FinanceLedger.id).label("count")
            )
            .where(FinanceLedger.business_date >= start_date)
            .where(FinanceLedger.business_date <= end_date)
            .group_by(FinanceLedger.category)
        )
        
        return {row.category: row.count for row in result.all()}
    
    # =========================================================================
    # LEDGER QUERIES
    # =========================================================================
    
    async def get_entries(
        self,
        category: str | None = None,
        business_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FinanceLedger]:
        """
        Get finance ledger entries with optional filters.
        """
        query = select(FinanceLedger)
        
        if category:
            query = query.where(FinanceLedger.category == category)
        if business_date:
            query = query.where(FinanceLedger.business_date == business_date)
        if start_date:
            query = query.where(FinanceLedger.business_date >= start_date)
        if end_date:
            query = query.where(FinanceLedger.business_date <= end_date)
        
        query = query.order_by(FinanceLedger.business_date.desc(), FinanceLedger.category)
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # =========================================================================
    # DAILY STAFF PAYROLL (Phase 6.1)
    # =========================================================================
    
    async def add_daily_staff_payroll(
        self,
        business_date: date,
        employees: list[dict],
        notes: str | None = None,
    ) -> FinanceLedger:
        """
        Add daily staff payroll entry.
        
        This creates a FinanceLedger entry with category=SALARY and is_payroll=True.
        The employee breakdown is stored in JSON for detailed reporting.
        
        Args:
            business_date: Date of work
            employees: List of employee dicts with:
                - name: str - Employee name
                - rate: Decimal - Daily rate (e.g., 1400.00)
                - hours: int - Hours worked (default 8)
                - amount: Decimal (optional) - Override calculated amount
            notes: Optional notes about the payroll
            
        Returns:
            Created FinanceLedger entry
            
        Raises:
            ValueError: If employees list is empty or invalid
            
        Example:
            employees = [
                {"name": "Арман", "rate": Decimal("1400"), "hours": 8},
                {"name": "Болат", "rate": Decimal("1000"), "hours": 4},
            ]
            # Total = 1400 + (1000 * 4/8) = 1400 + 500 = 1900
        """
        # Validate employees
        if not employees:
            raise ValueError("employees list cannot be empty")
        
        if len(employees) > 10:
            raise ValueError("Maximum 10 employees per payroll entry")
        
        # Process each employee
        processed_employees = []
        total_amount = Decimal("0")
        
        for emp in employees:
            name = emp.get("name", "Unknown")
            rate = Decimal(str(emp.get("rate", 0)))
            hours = float(emp.get("hours", 8))
            
            # Validate
            if rate <= Decimal("0"):
                raise ValueError(f"rate must be positive for employee '{name}'")
            if hours <= 0:
                raise ValueError(f"hours must be positive for employee '{name}'")
            if hours > 24:
                raise ValueError(f"hours cannot exceed 24 for employee '{name}'")
            
            # Calculate amount: rate (per hour) * hours
            # Rate is hourly rate (т/час), so: amount = rate * hours
            if "amount" in emp and emp["amount"] is not None:
                amount = Decimal(str(emp["amount"]))
            else:
                amount = (rate * Decimal(str(hours))).quantize(Decimal("0.01"))
            
            processed_employees.append({
                "name": name,
                "rate": str(rate),
                "hours": hours,
                "amount": str(amount),
            })
            
            total_amount += amount
        
        # Build breakdown JSON
        breakdown = {
            "employees": processed_employees,
            "total": str(total_amount),
        }
        
        # IDEMPOTENCY: Delete existing payroll entries for this date before creating new ones
        # This prevents duplication when "РАССЧИТАТЬ ВСЁ" is clicked multiple times
        from sqlalchemy import delete as sql_delete
        await self.session.execute(
            sql_delete(FinanceLedger).where(
                FinanceLedger.business_date == business_date,
                FinanceLedger.is_payroll == True,  # noqa: E712
            )
        )
        
        # Create entry
        entry = FinanceLedger(
            category=FinanceCategory.SALARY.value,
            amount=total_amount,
            business_date=business_date,
            description=f"Daily payroll for {len(employees)} employee(s)",
            is_payroll=True,
            employee_breakdown=breakdown,
            payroll_notes=notes,
        )
        
        self.session.add(entry)
        await self.session.flush()
        
        return entry
    
    async def get_daily_payroll(
        self,
        business_date: date,
    ) -> FinanceLedger | None:
        """
        Get payroll entry for a specific date.
        
        Args:
            business_date: Date to get payroll for
            
        Returns:
            FinanceLedger entry if found, None otherwise
        """
        result = await self.session.execute(
            select(FinanceLedger)
            .where(FinanceLedger.business_date == business_date)
            .where(FinanceLedger.is_payroll == True)  # noqa: E712
            .order_by(FinanceLedger.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def list_payroll_entries(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FinanceLedger]:
        """
        List payroll entries for a date range.
        
        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            limit: Maximum entries to return
            offset: Pagination offset
            
        Returns:
            List of payroll entries
        """
        query = (
            select(FinanceLedger)
            .where(FinanceLedger.is_payroll == True)  # noqa: E712
        )
        
        if start_date:
            query = query.where(FinanceLedger.business_date >= start_date)
        if end_date:
            query = query.where(FinanceLedger.business_date <= end_date)
        
        query = query.order_by(FinanceLedger.business_date.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # FIXED MONTHLY COSTS (Phase 6.3)
    # =========================================================================

    async def get_fixed_cost_settings(self) -> list[FixedCostSetting]:
        """Get all fixed cost settings."""
        result = await self.session.execute(
            select(FixedCostSetting).order_by(FixedCostSetting.category_name)
        )
        return list(result.scalars().all())

    async def update_fixed_cost_setting(
        self, 
        category_name: str, 
        monthly_amount: Decimal, 
        is_active: bool = True,
        description: str | None = None
    ) -> FixedCostSetting:
        """Create or update a fixed cost setting."""
        result = await self.session.execute(
            select(FixedCostSetting).where(FixedCostSetting.category_name == category_name)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.monthly_amount = monthly_amount
            setting.is_active = is_active
            if description is not None:
                setting.description = description
        else:
            setting = FixedCostSetting(
                category_name=category_name,
                monthly_amount=monthly_amount,
                is_active=is_active,
                description=description
            )
            self.session.add(setting)
            
        await self.session.flush()
        return setting

    async def allocate_daily_fixed_costs(self, business_date: date) -> list[FinanceLedger]:
        """
        Allocate daily share of fixed monthly costs.
        
        Formula: Daily = Monthly / Days_In_Month
        """
        # 1. Get days in month
        days_in_month = monthrange(business_date.year, business_date.month)[1]
        
        # 2. Get active settings
        result = await self.session.execute(
            select(FixedCostSetting).where(FixedCostSetting.is_active == True)  # noqa: E712
        )
        settings = result.scalars().all()
        
        entries = []
        
        for setting in settings:
            # Map name to FinanceCategory
            category_code = FinanceCategory.OTHER.value
            name_upper = setting.category_name.upper()
            
            if "АРЕНДА" in name_upper: category_code = FinanceCategory.RENT.value
            elif "ОХРАНА" in name_upper: category_code = FinanceCategory.SECURITY.value
            elif "ИНТЕРНЕТ" in name_upper: category_code = FinanceCategory.INTERNET.value
            elif "КОММУНАЛЬНЫЕ" in name_upper: category_code = FinanceCategory.UTILITIES.value
            elif "ЭЛЕКТРИЧЕСТВО" in name_upper: category_code = FinanceCategory.UTILITIES.value
            elif "БУХГАЛТЕР" in name_upper: category_code = FinanceCategory.OTHER.value
            
            # Calculate daily amount
            daily_amount = (setting.monthly_amount / Decimal(days_in_month)).quantize(Decimal("0.01"))
            
            if daily_amount <= 0:
                continue

            # Idempotency check: Use description to distinguish
            description = f"Daily Fixed Cost: {setting.category_name}"
            
            existing = await self.session.execute(
                select(FinanceLedger)
                .where(FinanceLedger.business_date == business_date)
                .where(FinanceLedger.description == description)
            )
            if existing.scalar_one_or_none():
                continue
                
            entry = FinanceLedger(
                category=category_code,
                amount=daily_amount,
                business_date=business_date,
                description=description
            )
            self.session.add(entry)
            entries.append(entry)
            
        await self.session.flush()
        return entries
