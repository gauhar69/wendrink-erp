"""
WENDRINK ERP - CSV Import Utilities

Import OPEX data from CSV files.
"""

import csv
import io
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance_ledger import FinanceCategory, FinanceLedger
from app.services.finance import FinanceService


@dataclass
class CSVImportResult:
    """Result of a CSV import operation."""
    success: bool
    year: int
    month: int
    days_in_month: int
    categories_imported: int
    entries_created: int
    total_monthly: Decimal
    total_daily_avg: Decimal
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CSVRow:
    """Parsed CSV row."""
    category: str
    monthly_amount: Decimal
    description: str | None


class CSVImporter:
    """
    Import monthly OPEX from CSV files.
    
    CSV Format:
    ```
    category,monthly_amount,description
    SALARY,756000,Staff salaries
    RENT,300000,Shop rental
    ```
    
    The importer:
    1. Validates each row
    2. Calculates daily allocation (Law 9)
    3. Creates finance_ledger entries for each day
    """
    
    VALID_CATEGORIES = [c.value for c in FinanceCategory]
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.finance_service = FinanceService(session)
    
    async def import_csv(
        self,
        csv_content: str,
        year: int,
        month: int,
        skip_existing: bool = True,
    ) -> CSVImportResult:
        """
        Import OPEX from CSV content.
        
        Args:
            csv_content: CSV string content
            year: Target year
            month: Target month
            skip_existing: Skip days that already have entries
            
        Returns:
            CSVImportResult with details
        """
        errors: list[str] = []
        warnings: list[str] = []
        
        # Validate month
        if not (1 <= month <= 12):
            return CSVImportResult(
                success=False,
                year=year,
                month=month,
                days_in_month=0,
                categories_imported=0,
                entries_created=0,
                total_monthly=Decimal("0"),
                total_daily_avg=Decimal("0"),
                errors=["Month must be between 1 and 12"],
            )
        
        days_in_month = monthrange(year, month)[1]
        
        # Parse CSV
        rows = self._parse_csv(csv_content, errors)
        
        if errors:
            return CSVImportResult(
                success=False,
                year=year,
                month=month,
                days_in_month=days_in_month,
                categories_imported=0,
                entries_created=0,
                total_monthly=Decimal("0"),
                total_daily_avg=Decimal("0"),
                errors=errors,
            )
        
        if not rows:
            return CSVImportResult(
                success=False,
                year=year,
                month=month,
                days_in_month=days_in_month,
                categories_imported=0,
                entries_created=0,
                total_monthly=Decimal("0"),
                total_daily_avg=Decimal("0"),
                errors=["No valid rows found in CSV"],
            )
        
        # Check for existing entries
        existing = await self.finance_service.check_month_exists(year, month)
        if existing and not skip_existing:
            warnings.append(
                f"Existing entries found for categories: {list(existing.keys())}. "
                "Set skip_existing=True to skip or handle manually."
            )
        
        # Import each category
        total_monthly = Decimal("0")
        total_entries = 0
        categories_imported = 0
        
        for row in rows:
            try:
                entries = await self.finance_service.allocate_monthly_opex(
                    category=row.category,
                    monthly_amount=row.monthly_amount,
                    year=year,
                    month=month,
                    description=row.description,
                    skip_existing=skip_existing,
                )
                
                if entries:
                    total_entries += len(entries)
                    total_monthly += row.monthly_amount
                    categories_imported += 1
                else:
                    warnings.append(f"Category {row.category}: all days already have entries")
                    
            except ValueError as e:
                errors.append(f"Category {row.category}: {str(e)}")
        
        # Calculate daily average
        daily_avg = total_monthly / Decimal(str(days_in_month)) if days_in_month > 0 else Decimal("0")
        
        return CSVImportResult(
            success=len(errors) == 0,
            year=year,
            month=month,
            days_in_month=days_in_month,
            categories_imported=categories_imported,
            entries_created=total_entries,
            total_monthly=total_monthly,
            total_daily_avg=daily_avg.quantize(Decimal("0.01")),
            errors=errors,
            warnings=warnings,
        )
    
    def _parse_csv(self, csv_content: str, errors: list[str]) -> list[CSVRow]:
        """
        Parse CSV content into validated rows.
        """
        rows: list[CSVRow] = []
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            errors.append(f"Failed to parse CSV: {str(e)}")
            return rows
        
        # Check required columns
        if not reader.fieldnames:
            errors.append("CSV has no headers")
            return rows
        
        required = {"category", "monthly_amount"}
        missing = required - set(reader.fieldnames)
        if missing:
            errors.append(f"Missing required columns: {missing}")
            return rows
        
        # Parse each row
        for i, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            try:
                parsed = self._parse_row(row, i)
                if parsed:
                    rows.append(parsed)
            except ValueError as e:
                errors.append(str(e))
        
        return rows
    
    def _parse_row(self, row: dict, line_num: int) -> CSVRow | None:
        """
        Parse and validate a single CSV row.
        """
        # Get category
        category = row.get("category", "").strip().upper()
        if not category:
            raise ValueError(f"Line {line_num}: category is required")
        
        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Line {line_num}: Invalid category '{category}'. "
                f"Must be one of: {self.VALID_CATEGORIES}"
            )
        
        # Get amount
        amount_str = row.get("monthly_amount", "").strip()
        if not amount_str:
            raise ValueError(f"Line {line_num}: monthly_amount is required")
        
        try:
            # Remove any thousand separators
            amount_str = amount_str.replace(",", "").replace(" ", "")
            amount = Decimal(amount_str)
        except InvalidOperation:
            raise ValueError(f"Line {line_num}: Invalid amount '{amount_str}'")
        
        if amount < Decimal("0"):
            raise ValueError(f"Line {line_num}: Amount cannot be negative")
        
        # Get optional description
        description = row.get("description", "").strip() or None
        
        return CSVRow(
            category=category,
            monthly_amount=amount,
            description=description,
        )
    
    def generate_template(self) -> str:
        """
        Generate a sample CSV template.
        """
        lines = [
            "category,monthly_amount,description",
            "SALARY,756000,Staff salaries",
            "RENT,300000,Shop rental",
            "UTILITIES,35000,Electricity and water",
            "SECURITY,55000,Security service",
            "INTERNET,15000,Internet connection",
            "EQUIPMENT,20000,Equipment maintenance",
            "SUPPLIES,5000,Cups napkins etc",
        ]
        return "\n".join(lines)
