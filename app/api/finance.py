"""
WENDRINK ERP - Finance API Endpoints

OPEX management and querying.

LAWS ENFORCED:
- Law 1: Ledger-First (OPEX = SUM of finance_ledger)
- Law 9: OPEX Allocation Across Daily Periods
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.finance_ledger import FinanceCategory
from app.schemas.finance import FinanceCreate, FinanceRead
from app.services.finance import FinanceService

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class DailyOPEXResponse(BaseModel):
    """Daily OPEX breakdown."""
    business_date: str
    total: str
    breakdown: dict[str, str]


class MonthlyOPEXResponse(BaseModel):
    """Monthly OPEX summary."""
    year: int
    month: int
    days_in_month: int
    total: str
    breakdown: dict[str, str]
    daily_average: str


class AllocationRequest(BaseModel):
    """Request to allocate monthly OPEX."""
    category: str = Field(..., description="OPEX category")
    monthly_amount: Decimal = Field(..., gt=0, description="Total monthly amount")
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    description: str | None = None
    skip_existing: bool = Field(True, description="Skip days with existing entries")


class AllocationResponse(BaseModel):
    """Response from OPEX allocation."""
    category: str
    year: int
    month: int
    monthly_amount: str
    daily_amount: str
    days_created: int
    message: str


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post(
    "",
    response_model=FinanceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Finance Entry",
)
async def create_finance_entry(
    data: FinanceCreate,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a single finance ledger entry.
    
    - **category**: OPEX category (SALARY, RENT, etc.)
    - **amount**: Daily amount in KZT
    - **business_date**: Date for the expense
    """
    service = FinanceService(session)
    
    try:
        entry = await service.create_entry(
            category=data.category,
            amount=data.amount,
            business_date=data.business_date,
            description=data.description,
        )
        
        await session.commit()
        await session.refresh(entry)
        
        return entry
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[FinanceRead],
    summary="List Finance Entries",
)
async def list_finance_entries(
    session: AsyncSession = Depends(get_db),
    category: str | None = None,
    business_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list:
    """
    Get finance ledger entries with optional filters.
    """
    service = FinanceService(session)
    entries = await service.get_entries(
        category=category,
        business_date=business_date,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    
    return entries


# ============================================================================
# OPEX Query Endpoints
# ============================================================================

@router.get(
    "/daily-opex/{business_date}",
    response_model=DailyOPEXResponse,
    summary="Get Daily OPEX",
)
async def get_daily_opex(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> DailyOPEXResponse:
    """
    Get total OPEX and breakdown for a specific business date.
    
    Returns all OPEX categories with their daily amounts.
    """
    service = FinanceService(session)
    opex = await service.get_daily_opex(business_date)
    
    return DailyOPEXResponse(
        business_date=str(opex.business_date),
        total=str(opex.total),
        breakdown={k: str(v) for k, v in opex.breakdown.items()},
    )


@router.get(
    "/monthly-opex/{year}/{month}",
    response_model=MonthlyOPEXResponse,
    summary="Get Monthly OPEX",
)
async def get_monthly_opex(
    year: int,
    month: int,
    session: AsyncSession = Depends(get_db),
) -> MonthlyOPEXResponse:
    """
    Get total OPEX for a month with category breakdown.
    """
    if not (1 <= month <= 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12",
        )
    
    service = FinanceService(session)
    opex = await service.get_monthly_opex(year, month)
    
    return MonthlyOPEXResponse(
        year=opex.year,
        month=opex.month,
        days_in_month=opex.days_in_month,
        total=str(opex.total),
        breakdown={k: str(v) for k, v in opex.breakdown.items()},
        daily_average=str(opex.daily_average.quantize(Decimal("0.01"))),
    )


@router.get(
    "/categories",
    summary="List OPEX Categories",
)
async def list_categories() -> dict:
    """
    Get all valid OPEX categories.
    """
    return {
        "categories": [c.value for c in FinanceCategory],
    }


# ============================================================================
# Monthly Allocation Endpoints
# ============================================================================

@router.post(
    "/allocate",
    response_model=AllocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate Monthly OPEX",
)
async def allocate_monthly_opex(
    data: AllocationRequest,
    session: AsyncSession = Depends(get_db),
) -> AllocationResponse:
    """
    Distribute monthly OPEX evenly across all days in the month.
    
    **Algorithm (Law 9):**
    ```
    daily_amount = monthly_amount / days_in_month
    ```
    
    **Example:**
    - Monthly salary: 756,000 KZT
    - January 2026: 31 days
    - Daily allocation: 24,387.10 KZT per day
    
    This creates one finance_ledger entry per day for the category.
    """
    service = FinanceService(session)
    
    try:
        entries = await service.allocate_monthly_opex(
            category=data.category,
            monthly_amount=data.monthly_amount,
            year=data.year,
            month=data.month,
            description=data.description,
            skip_existing=data.skip_existing,
        )
        
        await session.commit()
        
        # Calculate daily amount for response
        from calendar import monthrange
        days_in_month = monthrange(data.year, data.month)[1]
        daily_amount = (data.monthly_amount / Decimal(str(days_in_month))).quantize(Decimal("0.01"))
        
        return AllocationResponse(
            category=data.category,
            year=data.year,
            month=data.month,
            monthly_amount=str(data.monthly_amount),
            daily_amount=str(daily_amount),
            days_created=len(entries),
            message=f"Created {len(entries)} entries for {data.category}",
        )
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/check-month/{year}/{month}",
    summary="Check Month Entries",
)
async def check_month_entries(
    year: int,
    month: int,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Check if OPEX entries exist for a month.
    
    Useful before running allocation to avoid duplicates.
    """
    if not (1 <= month <= 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12",
        )
    
    service = FinanceService(session)
    existing = await service.check_month_exists(year, month)
    
    return {
        "year": year,
        "month": month,
        "has_entries": len(existing) > 0,
        "categories": existing,
    }


# ============================================================================
# CSV Import Endpoints
# ============================================================================

class CSVImportRequest(BaseModel):
    """Request to import OPEX from CSV."""
    csv_content: str = Field(..., description="CSV file content as string")
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    skip_existing: bool = Field(True, description="Skip days with existing entries")


class CSVImportResponse(BaseModel):
    """Response from CSV import."""
    success: bool
    year: int
    month: int
    days_in_month: int
    categories_imported: int
    entries_created: int
    total_monthly: str
    total_daily_avg: str
    errors: list[str]
    warnings: list[str]


@router.post(
    "/import-csv",
    response_model=CSVImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import OPEX from CSV",
)
async def import_csv(
    data: CSVImportRequest,
    session: AsyncSession = Depends(get_db),
) -> CSVImportResponse:
    """
    Import monthly OPEX from CSV content.
    
    **CSV Format:**
    ```csv
    category,monthly_amount,description
    SALARY,756000,Staff salaries
    RENT,300000,Shop rental
    UTILITIES,35000,Electricity and water
    ```
    
    **Valid Categories:**
    SALARY, RENT, UTILITIES, SECURITY, INTERNET, EQUIPMENT, SUPPLIES, MARKETING, OTHER
    
    **Process:**
    1. Parse and validate CSV
    2. Calculate daily allocation for each category
    3. Create finance_ledger entries for each day
    
    **Example:**
    Monthly salary: 756,000 KZT for January 2026 (31 days)
    Creates 31 entries of 24,387.10 KZT each
    """
    from app.utils.csv_import import CSVImporter
    
    importer = CSVImporter(session)
    
    result = await importer.import_csv(
        csv_content=data.csv_content,
        year=data.year,
        month=data.month,
        skip_existing=data.skip_existing,
    )
    
    if result.success:
        await session.commit()
    else:
        await session.rollback()
    
    return CSVImportResponse(
        success=result.success,
        year=result.year,
        month=result.month,
        days_in_month=result.days_in_month,
        categories_imported=result.categories_imported,
        entries_created=result.entries_created,
        total_monthly=str(result.total_monthly),
        total_daily_avg=str(result.total_daily_avg),
        errors=result.errors,
        warnings=result.warnings,
    )


@router.get(
    "/csv-template",
    summary="Get CSV Template",
)
async def get_csv_template() -> dict:
    """
    Get a sample CSV template for OPEX import.
    """
    from app.utils.csv_import import CSVImporter
    
    importer = CSVImporter(None)
    template = importer.generate_template()
    
    return {
        "template": template,
        "valid_categories": [c.value for c in FinanceCategory],
        "instructions": [
            "First row must be header: category,monthly_amount,description",
            "category must be one of the valid categories",
            "monthly_amount is the total for the entire month",
            "description is optional",
        ],
    }


# ============================================================================
# Daily Staff Payroll Endpoints (Phase 6.1)
# ============================================================================

class EmployeePayrollItem(BaseModel):
    """Single employee payroll item."""
    name: str = Field(..., min_length=1, max_length=100, description="Employee name")
    rate: Decimal = Field(..., gt=0, description="Daily rate in KZT")
    hours: float = Field(8.0, ge=0.5, le=24.0, description="Hours worked (0.5-24)")
    amount: Decimal | None = Field(None, description="Override calculated amount")


class DailyPayrollRequest(BaseModel):
    """Request to add daily staff payroll."""
    business_date: date = Field(..., description="Date of work")
    employees: list[EmployeePayrollItem] = Field(
        ..., 
        min_length=1, 
        max_length=10,
        description="List of employees and their pay"
    )
    notes: str | None = Field(None, max_length=500, description="Optional notes")


class EmployeePayrollResponse(BaseModel):
    """Employee payroll item in response."""
    name: str
    rate: str
    hours: float
    amount: str


class DailyPayrollResponse(BaseModel):
    """Response for daily payroll."""
    id: str
    business_date: str
    total_amount: str
    employee_count: int
    employees: list[EmployeePayrollResponse]
    notes: str | None
    created_at: str


@router.post(
    "/payroll",
    response_model=DailyPayrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Daily Staff Payroll",
)
async def add_daily_payroll(
    data: DailyPayrollRequest,
    session: AsyncSession = Depends(get_db),
) -> DailyPayrollResponse:
    """
    Add daily staff payroll.
    
    Creates a finance_ledger entry with category=SALARY and is_payroll=True.
    
    **Calculation:**
    - amount = rate × hours (rate is HOURLY, т/час)
    - Total = sum of all employee amounts
    
    **Example:**
    ```json
    {
        "business_date": "2026-02-02",
        "employees": [
            {"name": "Шахназ", "rate": 1000, "hours": 5},
            {"name": "Абулм", "rate": 1000, "hours": 5}
        ],
        "notes": "Дневная смена"
    }
    ```
    Total = (1000 × 5) + (1000 × 5) = 10000 KZT
    """
    service = FinanceService(session)
    
    try:
        # Convert Pydantic models to dicts
        employees = [
            {
                "name": emp.name,
                "rate": emp.rate,
                "hours": emp.hours,
                "amount": emp.amount,
            }
            for emp in data.employees
        ]
        
        entry = await service.add_daily_staff_payroll(
            business_date=data.business_date,
            employees=employees,
            notes=data.notes,
        )

        # Automatically allocate fixed costs for this day
        await service.allocate_daily_fixed_costs(data.business_date)

        from app.utils.cache import invalidate_cache
        invalidate_cache()

        await session.commit()
        await session.refresh(entry)
        
        # Build response
        breakdown = entry.employee_breakdown or {}
        emp_list = breakdown.get("employees", [])
        
        return DailyPayrollResponse(
            id=str(entry.id),
            business_date=str(entry.business_date),
            total_amount=str(entry.amount),
            employee_count=len(emp_list),
            employees=[
                EmployeePayrollResponse(
                    name=e["name"],
                    rate=e["rate"],
                    hours=e["hours"],
                    amount=e["amount"],
                )
                for e in emp_list
            ],
            notes=entry.payroll_notes,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        )
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/payroll/{business_date}",
    response_model=DailyPayrollResponse | None,
    summary="Get Daily Payroll",
)
async def get_daily_payroll(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> DailyPayrollResponse | dict:
    """
    Get payroll for a specific date.
    
    Returns the payroll entry with employee breakdown.
    Returns null if no payroll exists for the date.
    """
    service = FinanceService(session)
    entry = await service.get_daily_payroll(business_date)
    
    if entry is None:
        return None
    
    breakdown = entry.employee_breakdown or {}
    emp_list = breakdown.get("employees", [])
    
    return DailyPayrollResponse(
        id=str(entry.id),
        business_date=str(entry.business_date),
        total_amount=str(entry.amount),
        employee_count=len(emp_list),
        employees=[
            EmployeePayrollResponse(
                name=e["name"],
                rate=e["rate"],
                hours=e["hours"],
                amount=e["amount"],
            )
            for e in emp_list
        ],
        notes=entry.payroll_notes,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


class PayrollListResponse(BaseModel):
    """Response for payroll list."""
    count: int
    entries: list[DailyPayrollResponse]


@router.get(
    "/payroll",
    response_model=PayrollListResponse,
    summary="List Daily Payroll",
)
async def list_daily_payroll(
    session: AsyncSession = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> PayrollListResponse:
    """
    List payroll entries for a date range.
    
    Use start_date and end_date to filter by date range.
    """
    service = FinanceService(session)
    entries = await service.list_payroll_entries(
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    
    responses = []
    for entry in entries:
        breakdown = entry.employee_breakdown or {}
        emp_list = breakdown.get("employees", [])
        
        responses.append(DailyPayrollResponse(
            id=str(entry.id),
            business_date=str(entry.business_date),
            total_amount=str(entry.amount),
            employee_count=len(emp_list),
            employees=[
                EmployeePayrollResponse(
                    name=e["name"],
                    rate=e["rate"],
                    hours=e["hours"],
                    amount=e["amount"],
                )
                for e in emp_list
            ],
            notes=entry.payroll_notes,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        ))
    
    return PayrollListResponse(
        count=len(responses),
        entries=responses,
    )


# ============================================================================
# Fixed Monthly Costs Endpoints (Phase 6.3)
# ============================================================================

from app.schemas.finance import FixedCostSettingCreate, FixedCostSettingRead

@router.get(
    "/fixed-costs",
    response_model=list[FixedCostSettingRead],
    summary="List Fixed Cost Settings",
)
async def list_fixed_costs(
    session: AsyncSession = Depends(get_db),
) -> list:
    """Get all fixed monthly cost settings."""
    service = FinanceService(session)
    return await service.get_fixed_cost_settings()


@router.post(
    "/fixed-costs",
    response_model=FixedCostSettingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Fixed Cost",
)
async def update_fixed_cost(
    data: FixedCostSettingCreate,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create or update a fixed cost setting.
    
    If category_name exists, it updates the amount.
    If not, it creates a new setting.
    """
    service = FinanceService(session)
    
    setting = await service.update_fixed_cost_setting(
        category_name=data.category_name,
        monthly_amount=data.monthly_amount,
        is_active=data.is_active,
        description=data.description,
    )
    
    await session.commit()
    await session.refresh(setting)
    
    return setting

