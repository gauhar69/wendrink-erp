"""
WENDRINK ERP - Finance Ledger Model

APPEND-ONLY ledger for OPEX and other financial events.

CRITICAL RULES:
- ❌ NO UPDATE allowed
- ❌ NO DELETE allowed
- ✅ ONLY INSERT allowed
- Daily OPEX = SUM(amount) WHERE business_date = X
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class FinanceCategory(str, Enum):
    """Categories of financial events."""
    
    SALARY = "SALARY"           # Staff salaries
    RENT = "RENT"               # Premises rent
    UTILITIES = "UTILITIES"     # Electricity, water, gas
    SECURITY = "SECURITY"       # Security services
    INTERNET = "INTERNET"       # Internet and communication
    EQUIPMENT = "EQUIPMENT"     # Equipment maintenance
    SUPPLIES = "SUPPLIES"       # Consumables (cups, napkins)
    MARKETING = "MARKETING"     # Advertising, promotions
    OTHER = "OTHER"             # Miscellaneous expenses


class FinanceLedger(Base, UUIDMixin, TimestampMixin):
    """
    Finance Ledger - APPEND-ONLY event log for OPEX.
    
    This table tracks all operational expenses.
    Daily OPEX = SUM(amount) WHERE business_date = X
    
    ⚠️ NEVER UPDATE OR DELETE ROWS IN THIS TABLE ⚠️
    
    Corrections must be implemented as new compensating entries.
    
    Example (daily allocation from monthly):
    - Monthly salary: 756,000 KZT
    - Days in January: 31
    - Daily entry: 756,000 / 31 = 24,387.09 KZT
    
    Payroll entries (is_payroll=True):
    - Track daily staff wages with employee breakdown
    - employee_breakdown contains JSON with employee details
    """
    
    __tablename__ = "finance_ledger"

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="SALARY, RENT, UTILITIES, etc.",
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Amount in KZT (positive for expense)",
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional details about the expense",
    )
    
    business_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Almaty business date for P&L allocation",
    )
    
    # =========================================================================
    # PAYROLL FIELDS (Phase 6.1)
    # =========================================================================
    
    is_payroll: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if this is a daily staff payroll entry",
    )
    
    employee_breakdown: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON with employee payroll details: {employees: [...], total: '...'}",
    )
    
    payroll_notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Additional notes about the payroll (e.g., 'Болат worked half-shift')",
    )

    def __repr__(self) -> str:
        payroll_marker = " [PAYROLL]" if self.is_payroll else ""
        return f"<FinanceLedger(category={self.category}, amount={self.amount}, date={self.business_date}{payroll_marker})>"


class FixedCostSetting(Base, UUIDMixin, TimestampMixin):
    """
    Fixed Monthly Costs Configuration.
    
    Stores the monthly amount for fixed expenses (Rent, Internet, etc.).
    Used to calculate daily share: Daily = Monthly / Days_In_Month.
    """
    __tablename__ = "fixed_cost_settings"

    category_name: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False,
        comment="Name of the expense (e.g., 'Аренда')"
    )
    
    monthly_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Total monthly cost in KZT"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="If False, this cost is ignored in calculations"
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FixedCostSetting(name={self.category_name}, monthly={self.monthly_amount})>"

