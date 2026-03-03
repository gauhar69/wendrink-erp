"""
WENDRINK ERP - Inventory API Endpoints

Supply, balance, adjustment, and correction operations.

LAWS ENFORCED:
- Law 1: Ledger-First (balance = SUM of ledger)
- Law 5: Negative Stock Allowed
- Law 6: Corrections are Inserts
- Law 8: WAC Calculation
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.ingredient import Ingredient
from app.schemas.inventory import InventoryLedgerRead
from app.services.inventory import InventoryService

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class SupplyRequest(BaseModel):
    """Request to record a supply."""
    ingredient_id: UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity received")
    total_cost: Decimal = Field(..., ge=0, description="Total invoice cost")
    business_date: date | None = Field(None, description="Business date (defaults to today)")


class SupplyResponse(BaseModel):
    """Response from a supply operation."""
    id: str
    ingredient_id: str
    quantity: str
    unit_cost: str
    new_wac: str
    new_balance: str
    message: str


class BalanceResponse(BaseModel):
    """Inventory balance for an ingredient."""
    ingredient_id: str
    ingredient_name: str
    unit: str
    balance: str
    weighted_average_cost: str
    total_value: str
    position_number: int | None = None


class AdjustmentRequest(BaseModel):
    """Request for manual stock adjustment."""
    ingredient_id: UUID
    quantity_change: Decimal = Field(..., description="Change amount (+/-)")
    reason: str = Field(..., min_length=1, max_length=500)
    business_date: date | None = None


class WasteRequest(BaseModel):
    """Request for waste/spoilage."""
    ingredient_id: UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity wasted")
    reason: str = Field(..., min_length=1, max_length=500)
    business_date: date | None = None


class CorrectionRequest(BaseModel):
    """Request to correct an erroneous ledger entry."""
    original_entry_id: UUID
    correction_amount: Decimal = Field(..., description="Compensating amount (+/-)")
    reason: str = Field(..., min_length=1, max_length=500)


# ============================================================================
# Supply Endpoints
# ============================================================================

@router.post(
    "/supply",
    response_model=SupplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Supply",
)
async def record_supply(
    data: SupplyRequest,
    session: AsyncSession = Depends(get_db),
) -> SupplyResponse:
    """
    Record a supply (goods received) with WAC calculation.
    
    This operation:
    1. Calculates the new Weighted Average Cost
    2. Creates an inventory ledger entry
    3. Updates available stock
    
    WAC Formula:
    ```
    new_wac = (old_stock * old_wac + new_qty * new_unit_cost) / total_qty
    ```
    """
    # Verify ingredient exists
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == data.ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {data.ingredient_id} not found",
        )
    
    service = InventoryService(session)
    
    try:
        entry = await service.record_supply(
            ingredient_id=data.ingredient_id,
            quantity=data.quantity,
            total_cost=data.total_cost,
            business_date=data.business_date,
        )
        
        await session.commit()
        
        # Invalidate cache — inventory changed
        from app.utils.cache import invalidate_cache
        invalidate_cache()
        
        # Get new balance
        new_balance = await service.get_stock_balance(data.ingredient_id)
        
        return SupplyResponse(
            id=str(entry.id),
            ingredient_id=str(entry.ingredient_id),
            quantity=str(entry.change_amount),
            unit_cost=str(entry.unit_cost),
            new_wac=str(entry.weighted_average_cost),
            new_balance=str(new_balance),
            message=f"Supply recorded. New WAC: {entry.weighted_average_cost}",
        )
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Balance Endpoints
# ============================================================================

@router.get(
    "/balance",
    response_model=list[BalanceResponse],
    summary="Get All Balances",
)
async def get_all_balances(
    session: AsyncSession = Depends(get_db),
) -> list[BalanceResponse]:
    """
    Get current stock balance and WAC for all ingredients.
    
    Balance is calculated as SUM(change_amount) from the inventory ledger.
    This is the ONLY way to determine current stock (Law 1).
    """
    service = InventoryService(session)
    balances = await service.get_all_balances()
    
    return [
        BalanceResponse(
            ingredient_id=str(b["ingredient_id"]),
            ingredient_name=b["name"],
            unit=b["unit"],
            balance=str(b["balance"]),
            weighted_average_cost=str(b["weighted_average_cost"]),
            total_value=str(b["total_value"]),
        )
        for b in balances
    ]


@router.get(
    "/balance-at-date",
    response_model=list[BalanceResponse],
    summary="Get Balances at Date",
)
async def get_balances_at_date(
    target_date: date = Query(..., description="Date to get balances for (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_db),
) -> list[BalanceResponse]:
    """
    Get stock balance and WAC for all ingredients AS OF a specific date.

    Balance = SUM(change_amount) WHERE business_date <= target_date
    WAC = latest weighted_average_cost up to target_date

    This correctly shows historical balances without future operations affecting the result.
    """
    service = InventoryService(session)
    balances = await service.get_all_balances_at_date(target_date)

    return [
        BalanceResponse(
            ingredient_id=str(b["ingredient_id"]),
            ingredient_name=b["name"],
            unit=b["unit"],
            balance=str(b["balance"]),
            weighted_average_cost=str(b["weighted_average_cost"]),
            total_value=str(b["total_value"]),
            position_number=b.get("position_number"),
        )
        for b in balances
    ]


@router.get(
    "/balance/{ingredient_id}",
    response_model=BalanceResponse,
    summary="Get Ingredient Balance",
)
async def get_ingredient_balance(
    ingredient_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> BalanceResponse:
    """Get current stock balance and WAC for a specific ingredient."""
    # Verify ingredient exists
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} not found",
        )
    
    service = InventoryService(session)
    balance = await service.get_stock_balance(ingredient_id)
    wac = await service.get_current_wac(ingredient_id) or Decimal("0")
    value = balance * wac if balance > 0 else Decimal("0")
    
    return BalanceResponse(
        ingredient_id=str(ingredient_id),
        ingredient_name=ingredient.name,
        unit=ingredient.unit,
        balance=str(balance),
        weighted_average_cost=str(wac),
        total_value=str(value),
    )


# ============================================================================
# Ledger Endpoints
# ============================================================================

@router.get(
    "/ledger",
    response_model=list[InventoryLedgerRead],
    summary="Get Inventory Ledger",
)
async def get_ledger(
    session: AsyncSession = Depends(get_db),
    ingredient_id: UUID | None = None,
    event_type: str | None = None,
    business_date: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list:
    """
    Get inventory ledger entries with optional filters.
    
    This is the full audit trail of all inventory movements.
    """
    service = InventoryService(session)
    entries = await service.get_ledger_entries(
        ingredient_id=ingredient_id,
        event_type=event_type,
        business_date=business_date,
        limit=limit,
        offset=offset,
    )
    
    return entries


# ============================================================================
# Adjustment Endpoints
# ============================================================================

@router.post(
    "/adjustment",
    response_model=InventoryLedgerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Adjustment",
)
async def record_adjustment(
    data: AdjustmentRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record a manual stock adjustment.
    
    Use for:
    - Stocktake corrections
    - Spoilage
    - Breakage
    - Any non-sale/non-supply changes
    
    A reason is REQUIRED for audit purposes.
    """
    # Verify ingredient exists
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == data.ingredient_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {data.ingredient_id} not found",
        )
    
    service = InventoryService(session)
    
    try:
        entry = await service.record_adjustment(
            ingredient_id=data.ingredient_id,
            quantity_change=data.quantity_change,
            reason=data.reason,
            business_date=data.business_date,
        )
        
        await session.commit()
        await session.refresh(entry)
        
        from app.utils.cache import invalidate_cache
        invalidate_cache()
        
        return entry
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Waste Endpoints
# ============================================================================

@router.post(
    "/waste",
    status_code=status.HTTP_201_CREATED,
    summary="Record Waste",
)
async def record_waste(
    data: WasteRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Record a waste/spoilage."""
    result = await session.execute(
        select(Ingredient).where(Ingredient.id == data.ingredient_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {data.ingredient_id} not found",
        )
    
    service = InventoryService(session)
    
    try:
        entry = await service.record_waste(
            ingredient_id=data.ingredient_id,
            quantity=data.quantity,
            reason=data.reason,
            business_date=data.business_date,
        )
        
        await session.commit()
        await session.refresh(entry)
        
        from app.utils.cache import invalidate_cache
        invalidate_cache()
        
        return entry
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

# ============================================================================
# Correction Endpoints (Law 6: Corrections are Inserts)
# ============================================================================

@router.post(
    "/correction",
    response_model=InventoryLedgerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Correction",
)
async def record_correction(
    data: CorrectionRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Record a correction for an erroneous ledger entry.
    
    **IMPORTANT: This does NOT update or delete the original entry.**
    
    Instead, it creates a new compensating entry that:
    - References the original entry via event_id
    - Uses the SAME business_date as the original
    - Uses the SAME weighted_average_cost as the original
    
    Example:
    - Original (wrong): SALE -100g
    - Should have been: SALE -30g
    - Correction: +70g (compensates the error)
    - Result: SUM = -100 + 70 = -30 ✓
    """
    service = InventoryService(session)
    
    try:
        entry = await service.record_correction(
            original_entry_id=data.original_entry_id,
            correction_amount=data.correction_amount,
            reason=data.reason,
        )
        
        await session.commit()
        await session.refresh(entry)
        
        from app.utils.cache import invalidate_cache
        invalidate_cache()
        
        return entry
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Reporting Endpoints
# ============================================================================

@router.get(
    "/daily-cogs/{business_date}",
    summary="Get Daily COGS",
)
async def get_daily_cogs(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get total Cost of Goods Sold for a business date.
    
    COGS = SUM(cost_snapshot) for all SALE events on the date.
    """
    service = InventoryService(session)
    cogs = await service.get_daily_cogs(business_date)
    
    return {
        "business_date": str(business_date),
        "total_cogs": str(cogs),
    }


# ============================================================================
# Bulk Supply Endpoints (Invoice Import)
# ============================================================================

class BulkSupplyItemRequest(BaseModel):
    """Single item in a bulk supply invoice."""
    ingredient_id: UUID | None = Field(None, description="Ingredient UUID")
    ingredient_name: str | None = Field(None, max_length=100, description="Exact ingredient name")
    quantity_packs: Decimal = Field(..., gt=0, description="Number of packages")
    price_per_pack: Decimal = Field(..., gt=0, description="Price per package in KZT")


class BulkSupplyRequest(BaseModel):
    """Complete supply invoice."""
    business_date: date = Field(..., description="Invoice date (YYYY-MM-DD)")
    supplier_note: str | None = Field(None, max_length=500, description="Invoice notes")
    items: list[BulkSupplyItemRequest] = Field(..., min_length=1, description="Supply items")
    total_expected: Decimal = Field(..., gt=0, description="Expected total for verification")


class BulkSupplyItemResponse(BaseModel):
    """Result for a single supply item."""
    ingredient_id: str
    ingredient_name: str
    quantity_packs: str
    quantity_base_units: str
    price_per_pack: str
    line_total: str
    unit_cost: str
    new_wac: str


class BulkSupplyResponse(BaseModel):
    """Response after processing bulk supply."""
    status: str = "success"
    business_date: str
    supplier_note: str | None
    items_count: int
    total_calculated: str
    total_expected: str
    items: list[BulkSupplyItemResponse]
    ledger_ids: list[str]


@router.post(
    "/supply/bulk",
    response_model=BulkSupplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk Supply Import",
    description="""
    Import a complete supply invoice with multiple items.
    
    **Features:**
    - Supports lookup by ingredient_id (UUID) OR ingredient_name (exact match)
    - Validates total_expected matches sum of items
    - All items processed in atomic transaction (all-or-nothing)
    - WAC recalculated for each ingredient
    
    **Validation Rules:**
    - If ingredient not found → 409 error, entire invoice rejected
    - If total doesn't match → 422 error, entire invoice rejected
    - quantity_packs and price_per_pack must be > 0
    
    **Example (2 items):**
    ```json
    {
      "business_date": "2026-02-06",
      "supplier_note": "Invoice #127",
      "items": [
        {"ingredient_name": "Молоко", "quantity_packs": 10, "price_per_pack": 500},
        {"ingredient_name": "Какао", "quantity_packs": 5, "price_per_pack": 1000}
      ],
      "total_expected": 10000
    }
    ```
    """,
)
async def bulk_supply(
    data: BulkSupplyRequest,
    session: AsyncSession = Depends(get_db),
) -> BulkSupplyResponse:
    """
    Import a complete supply invoice.
    
    Works with single item (for mobile/simple forms) or many items (full invoice).
    """
    service = InventoryService(session)
    
    # Convert Pydantic models to dicts for service
    items = [
        {
            "ingredient_id": str(item.ingredient_id) if item.ingredient_id else None,
            "ingredient_name": item.ingredient_name,
            "quantity_packs": item.quantity_packs,
            "price_per_pack": item.price_per_pack,
        }
        for item in data.items
    ]
    
    try:
        result = await service.create_bulk_supply(
            items=items,
            business_date=data.business_date,
            total_expected=data.total_expected,
            supplier_note=data.supplier_note,
        )
        
        await session.commit()
        
        return BulkSupplyResponse(
            status=result["status"],
            business_date=result["business_date"],
            supplier_note=result["supplier_note"],
            items_count=result["items_count"],
            total_calculated=result["total_calculated"],
            total_expected=result["total_expected"],
            items=[BulkSupplyItemResponse(**item) for item in result["items"]],
            ledger_ids=result["ledger_ids"],
        )
        
    except ValueError as e:
        await session.rollback()
        error_msg = str(e)
        
        # Determine HTTP status based on error type
        if "не найден" in error_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


@router.post(
    "/supply/import-csv",
    response_model=BulkSupplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import Supply from CSV",
    description="""
    Import supply invoice from a CSV file.
    
    **CSV Format:**
    ```csv
    ingredient_name,quantity_packs,price_per_pack
    Молоко,10,500
    Какао,5,1000
    ```
    
    OR with ingredient_id:
    ```csv
    ingredient_id,quantity_packs,price_per_pack
    550e8400-e29b-41d4-a716-446655440001,10,500
    ```
    
    **Required columns:** quantity_packs, price_per_pack
    **Optional columns:** ingredient_id OR ingredient_name (at least one required)
    
    **Form parameters:**
    - file: CSV file
    - business_date: Invoice date (YYYY-MM-DD)
    - total_expected: Expected total for verification
    - supplier_note: Optional invoice notes
    """,
)
async def import_csv_supply(
    file: UploadFile,
    business_date: date = Form(..., description="Invoice date"),
    total_expected: Decimal = Form(..., description="Expected total"),
    supplier_note: str | None = Form(None, description="Invoice notes"),
    session: AsyncSession = Depends(get_db),
) -> BulkSupplyResponse:
    """
    Import supply invoice from CSV file.
    """
    import csv
    import io
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are supported"
        )
    
    # Read and parse CSV
    try:
        content = await file.read()
        text = content.decode('utf-8-sig')  # Handle BOM from Excel
        reader = csv.DictReader(io.StringIO(text))
        
        items = []
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            # Check for required columns
            if 'quantity_packs' not in row or 'price_per_pack' not in row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV missing required columns: quantity_packs, price_per_pack"
                )
            
            item = {
                "quantity_packs": Decimal(row['quantity_packs'].strip()),
                "price_per_pack": Decimal(row['price_per_pack'].strip()),
            }
            
            # Get ingredient identifier (ID or name)
            if 'ingredient_id' in row and row['ingredient_id'].strip():
                item["ingredient_id"] = row['ingredient_id'].strip()
            elif 'ingredient_name' in row and row['ingredient_name'].strip():
                item["ingredient_name"] = row['ingredient_name'].strip()
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {row_num}: missing ingredient_id or ingredient_name"
                )
            
            items.append(item)
        
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is empty or has no data rows"
            )
            
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV parsing error: {str(e)}"
        )
    
    # Process using bulk supply service
    service = InventoryService(session)
    
    try:
        result = await service.create_bulk_supply(
            items=items,
            business_date=business_date,
            total_expected=total_expected,
            supplier_note=supplier_note,
        )
        
        await session.commit()
        
        return BulkSupplyResponse(
            status=result["status"],
            business_date=result["business_date"],
            supplier_note=result["supplier_note"],
            items_count=result["items_count"],
            total_calculated=result["total_calculated"],
            total_expected=result["total_expected"],
            items=[BulkSupplyItemResponse(**item) for item in result["items"]],
            ledger_ids=result["ledger_ids"],
        )
        
    except ValueError as e:
        await session.rollback()
        error_msg = str(e)
        
        if "не найден" in error_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


# ============================================================================
# Supply History
# ============================================================================

@router.get(
    "/supply/history",
    summary="Get Supply History",
    description="Returns recent supply events grouped by date and provider (simulated grouping)."
)
async def get_supply_history(
    limit: int = 20,
    session: AsyncSession = Depends(get_db)
):
    """
    Get recent supply history. 
    Since we store individual ledger entries, we'll return them.
    Ideally we would group them by a transaction ID or metadata, but for MVP 
    we listing distinct days/providers or just raw entries.
    
    Current implementation: List most recent SUPPLY events.
    """
    from app.models.inventory_ledger import InventoryLedger
    from sqlalchemy import desc
    
    # Simple query for now: Get recent SUPPLY events
    # To properly group by "Purchase", we might need a common ID in future
    # For now, we return individual items or group by (date, created_at) approx.
    
    stmt = (
        select(InventoryLedger)
        .where(InventoryLedger.event_type == 'SUPPLY')
        .order_by(desc(InventoryLedger.created_at))
        .limit(100)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    
    # Mock grouping by (date, provider_note)
    # We use 'reason' or 'supplier_note' if available. 
    # Current ledger model might not have 'provider'.
    # We will just list them.
    
    # Check if ledger has 'reason' field populated with provider info?
    # record_supply doesn't easily store provider name in a separate column.
    # It might be in 'reason' or similar if we modified it.
    
    # Let's return flat list for now, client can group.
    
    history = []
    
    # Simplistic grouping by Day + Hour (assuming bulk upload happens at once)
    from itertools import groupby
    
    def group_key(r):
        return (r.business_date, r.created_at.strftime("%Y-%m-%d %H:%M"))

    rows_sorted = sorted(rows, key=group_key, reverse=True)
    
    for key, group in groupby(rows_sorted, key=group_key):
        items = list(group)
        first = items[0]
        total = sum(i.change_amount * i.unit_cost for i in items)
        
        history.append({
            "date": first.business_date.isoformat(),
            "provider": "Unknown (Bulk)", # We don't distinctly store provider yet in Ledger
            "items_count": len(items),
            "total_amount": str(total)
        })
        
        if len(history) >= limit:
            break
            
    return history

class InventoryAdjustment(BaseModel):
    ingredient_id: UUID
    quantity: Decimal = Field(..., description="New ACTUAL quantity")
    adjustment_type: str = "INVENTORY" 
    notes: str | None = None

class PurchaseItem(BaseModel):
    ingredient_name: str
    quantity: Decimal
    unit_cost: Decimal
    notes: str | None = None

@router.post("/inventory/manual-adjustment", summary="Manual Stock Adjustment (Set Absolute)")
async def manual_inventory_adjustment(
    adjustments: list[InventoryAdjustment],
    session: AsyncSession = Depends(get_db),
):
    """
    Set absolute stock quantity (Stocktake logic).
    Calculates difference from current balance and writes adjustment.
    """
    service = InventoryService(session)
    count = 0
    
    for adj in adjustments:
        # Get current balance
        current = await service.get_stock_balance(adj.ingredient_id)
        
        # Calculate difference
        diff = adj.quantity - current
        
        if diff == 0:
            continue
            
        # Record adjustment
        # Note: 'record_adjustment' handles the ledger entry creation
        await service.record_adjustment(
            ingredient_id=adj.ingredient_id,
            quantity_change=diff,
            reason=adj.notes or f"Manual Set: {current} -> {adj.quantity}",
            business_date=date.today()
        )
        count += 1
    
    await session.commit()
    return {"status": "success", "adjusted": count}

@router.post("/inventory/bulk-purchase-simple", summary="Simple Bulk Purchase")
async def bulk_purchase_simple(
    purchases: list[PurchaseItem],
    purchase_date: date,
    session: AsyncSession = Depends(get_db),
):
    """
    Record bulk purchase using simple Quantity + Unit Cost.
    Finds ingredient by Name.
    """
    service = InventoryService(session)
    count = 0
    
    for item in purchases:
        # Find ingredient by name
        stmt = select(Ingredient).where(Ingredient.name == item.ingredient_name)
        result = await session.execute(stmt)
        ingredient = result.scalar_one_or_none()
        
        if not ingredient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Ingredient '{item.ingredient_name}' not found"
            )

        # Record supply (using service to handle WAC properly)
        total = item.quantity * item.unit_cost
        
        await service.record_supply(
            ingredient_id=ingredient.id,
            quantity=item.quantity,
            total_cost=total,
            business_date=purchase_date
        )
        count += 1
        
    await session.commit()
    return {"status": "success", "items_added": count}
