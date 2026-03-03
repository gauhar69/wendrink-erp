"""
WENDRINK ERP - Data Verification API
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ConfigDict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.inventory_ledger import InventoryLedger, InventoryEventType
from app.models.sale import Sale
from app.models.ingredient import Ingredient
from app.models.finance_ledger import FinanceLedger
from app.schemas.base import BaseSchema

router = APIRouter(prefix="/verification", tags=["Verification"])

# --- Schemas ---

class DailySummary(BaseSchema):
    date: date
    revenue: Decimal
    cogs_sales: Decimal
    cogs_ledger: Decimal
    opex: Decimal
    net_profit: Decimal
    discrepancy: bool
    discrepancy_amount: Decimal

class VerificationSaleItem(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal
    revenue: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    profit: Decimal

class IngredientDayDetail(BaseSchema):
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    start_balance: Decimal
    total_in: Decimal
    total_out: Decimal
    end_balance: Decimal
    cost_impact: Decimal

class DailyDetailResponse(BaseSchema):
    sales: List[VerificationSaleItem]
    ingredients: List[IngredientDayDetail]

class IngredientDrilldownSummary(BaseSchema):
    start_balance: Decimal
    total_in: Decimal
    total_out: Decimal
    end_balance: Decimal
    avg_wac: Decimal
    total_cost: Decimal

class LedgerEntryWithBalance(BaseSchema):
    id: UUID
    timestamp: datetime
    event_type: str
    change_amount: Decimal
    cost_snapshot: Decimal
    memo: Optional[str] = None
    running_balance: Decimal
    wac_at_time: Decimal

class IngredientDrilldownResponse(BaseSchema):
    summary: IngredientDrilldownSummary
    entries: List[LedgerEntryWithBalance]

# --- Endpoints ---

@router.get("/daily-summary/{day}", response_model=DailySummary)
async def get_daily_summary(
    day: date,
    session: AsyncSession = Depends(get_db)
):
    """
    Get financial summary and verify ledger consistency.
    """
    # 1. Sales Data
    sales_q = select(
        func.sum(Sale.total_amount).label("revenue"),
        func.sum(Sale.total_cost).label("cogs")
    ).where(Sale.business_date == day)
    sales_res = (await session.execute(sales_q)).one()
    revenue = sales_res.revenue or Decimal(0)
    cogs_sales = sales_res.cogs or Decimal(0)
    
    # 2. Ledger Data (COGS from inventory movement)
    ledger_q = select(
        func.sum(InventoryLedger.cost_snapshot)
    ).where(
        and_(
            InventoryLedger.business_date == day,
            InventoryLedger.event_type == InventoryEventType.SALE.value
        )
    )
    cogs_ledger = (await session.execute(ledger_q)).scalar() or Decimal(0)
    
    # 3. OPEX
    opex_q = select(func.sum(FinanceLedger.amount)).where(FinanceLedger.business_date == day)
    opex = (await session.execute(opex_q)).scalar() or Decimal(0)
    
    # 4. Profit
    net_profit = revenue - cogs_ledger - opex
    
    # 5. Check Discrepancy
    diff = abs(cogs_sales - cogs_ledger)
    is_discrepancy = diff > Decimal("0.01")
    
    return DailySummary(
        date=day,
        revenue=revenue,
        cogs_sales=cogs_sales,
        cogs_ledger=cogs_ledger,
        opex=opex,
        net_profit=net_profit,
        discrepancy=is_discrepancy,
        discrepancy_amount=cogs_sales - cogs_ledger
    )

@router.get("/daily-detail/{day}", response_model=DailyDetailResponse)
async def get_daily_detail(
    day: date,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed breakdown of Sales and Ingredient usage for the day.
    """
    # 1. SALES DETAILS
    from app.services.analytics import AnalyticsService
    analytics = AnalyticsService(session)
    report = await analytics.get_product_profitability(day)
    
    sales_items = []
    for p in report.products:
        qty = p.quantity_sold
        if qty == 0: continue
        
        unit_cost = (p.cogs / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal(0)
        price = (p.revenue / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal(0)
        
        sales_items.append(VerificationSaleItem(
            product_id=p.product_id,
            product_name=p.product_name,
            quantity=qty,
            price=price,
            revenue=p.revenue,
            unit_cost=unit_cost,
            total_cost=p.cogs,
            profit=p.profit
        ))

    # 2. INGREDIENT MOVEMENTS
    ingredients = (await session.execute(select(Ingredient).order_by(Ingredient.name))).scalars().all()
    
    # Previous Balance (Sum < day)
    prev_bal_q = select(
        InventoryLedger.ingredient_id,
        func.sum(InventoryLedger.change_amount).label("bal")
    ).where(InventoryLedger.business_date < day).group_by(InventoryLedger.ingredient_id)
    
    prev_bal_res = (await session.execute(prev_bal_q)).all()
    prev_bal_map = {row.ingredient_id: (row.bal or Decimal(0)) for row in prev_bal_res}
    
    # Current Day Movements
    curr_mov_q = select(InventoryLedger).where(InventoryLedger.business_date == day)
    curr_rows = (await session.execute(curr_mov_q)).scalars().all()
    
    # Process in memory
    movements = {}
    for row in curr_rows:
        iid = row.ingredient_id
        if iid not in movements:
            movements[iid] = {"in": Decimal(0), "out": Decimal(0), "cost": Decimal(0)}
        
        amt = row.change_amount
        if amt > 0:
            movements[iid]["in"] += amt
        else:
            movements[iid]["out"] += amt
            
        if row.event_type == InventoryEventType.SALE.value:
            movements[iid]["cost"] += row.cost_snapshot
            
    ing_result = []
    for ing in ingredients:
        start = prev_bal_map.get(ing.id) or Decimal(0)
        mov = movements.get(ing.id) or {"in": Decimal(0), "out": Decimal(0), "cost": Decimal(0)}
        
        end = start + mov["in"] + mov["out"]
        
        # Skip items with no activity and 0 balance
        if start == 0 and mov["in"] == 0 and mov["out"] == 0:
            continue
            
        ing_result.append(IngredientDayDetail(
            ingredient_id=ing.id,
            ingredient_name=ing.name,
            unit=ing.unit,
            start_balance=start,
            total_in=mov["in"],
            total_out=mov["out"],
            end_balance=end,
            cost_impact=mov["cost"]
        ))
        
    return DailyDetailResponse(
        sales=sales_items,
        ingredients=ing_result
    )

@router.get("/ingredient-detail/{ingredient_id}/{day}", response_model=IngredientDrilldownResponse)
async def get_ingredient_drilldown(
    ingredient_id: UUID, 
    day: date, 
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed drilldown for an ingredient on a specific day with running balances.
    """
    # 1. Get Start Balance (Sum < day)
    start_bal_q = select(func.sum(InventoryLedger.change_amount)).where(
        and_(
            InventoryLedger.ingredient_id == ingredient_id,
            InventoryLedger.business_date < day
        )
    )
    start_balance = (await session.execute(start_bal_q)).scalar() or Decimal(0)

    # 2. Get Day Entries
    entries_q = select(InventoryLedger).where(
        and_(
            InventoryLedger.ingredient_id == ingredient_id,
            InventoryLedger.business_date == day
        )
    ).order_by(InventoryLedger.created_at)
    
    entries = (await session.execute(entries_q)).scalars().all()
    
    # 3. Calculate Running Balances
    current_bal = start_balance
    processed_entries = []
    total_in = Decimal(0)
    total_out = Decimal(0)
    total_cost = Decimal(0)
    
    for e in entries:
        current_bal += e.change_amount
        if e.change_amount > 0:
            total_in += e.change_amount
        else:
            total_out += e.change_amount # negative
            if e.event_type == InventoryEventType.SALE.value:
                total_cost += e.cost_snapshot

        processed_entries.append(LedgerEntryWithBalance(
            id=e.id,
            timestamp=e.created_at,
            event_type=e.event_type,
            change_amount=e.change_amount,
            cost_snapshot=e.cost_snapshot,
            memo=e.reason,
            running_balance=current_bal,
            wac_at_time=e.weighted_average_cost
        ))

    return IngredientDrilldownResponse(
        summary=IngredientDrilldownSummary(
            start_balance=start_balance,
            total_in=total_in,
            total_out=total_out,
            end_balance=current_bal,
            avg_wac=entries[0].weighted_average_cost if entries else Decimal(0),
            total_cost=total_cost
        ),
        entries=processed_entries
    )
