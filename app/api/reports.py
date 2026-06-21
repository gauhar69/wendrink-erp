"""
WENDRINK ERP - Reports API Endpoints

P&L reporting and analytics.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.analytics import AnalyticsService
from app.services.pnl import PLService

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class DailyPLResponse(BaseModel):
    """Daily P&L response."""
    business_date: str
    
    # Revenue
    revenue: str
    transaction_count: int
    
    # COGS
    cogs: str
    
    # Gross Profit
    gross_profit: str
    gross_margin_percent: str
    
    # Waste
    waste_amount: str
    
    # OPEX
    opex: dict  # {total: str, breakdown: {category: str}}
    
    # Net Profit
    net_profit: str
    net_margin_percent: str
    
    # Status
    is_profitable: bool


class MonthlyPLResponse(BaseModel):
    """Monthly P&L response."""
    year: int
    month: int
    days_in_month: int
    
    # Totals
    revenue: str
    transaction_count: int
    cogs: str
    gross_profit: str
    gross_margin_percent: str
    waste_amount: str
    opex_total: str
    opex_breakdown: dict[str, str]
    net_profit: str
    net_margin_percent: str
    
    # Averages
    avg_daily_revenue: str
    avg_daily_cogs: str
    avg_daily_opex: str
    avg_daily_net_profit: str
    
    # Status
    is_profitable: bool


class PLRangeResponse(BaseModel):
    """P&L range response."""
    start_date: str
    end_date: str
    days: int
    
    revenue: str
    cogs: str
    gross_profit: str
    gross_margin_percent: str
    waste_amount: str
    opex_total: str
    net_profit: str
    net_margin_percent: str
    
    is_profitable: bool


# ============================================================================
# Daily P&L Endpoints
# ============================================================================

@router.get(
    "/daily-pnl/{business_date}",
    response_model=DailyPLResponse,
    summary="Get Daily P&L",
)
async def get_daily_pnl(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> DailyPLResponse:
    """
    Get full Profit & Loss statement for a business date.
    
    **Formula:**
    ```
    Gross Profit = Revenue - COGS
    Net Profit = Gross Profit - OPEX
    ```
    
    **Example (WENDRINK):**
    ```
    Revenue:      18,250.00 KZT
    - COGS:       (5,251.00) KZT
    = Gross:      12,999.00 KZT (71% margin)
    - OPEX:      (38,258.05) KZT
    = Net:       (25,259.05) KZT (daily loss)
    ```
    """
    service = PLService(session)
    pl = await service.get_daily_pl(business_date)
    
    return DailyPLResponse(
        business_date=str(pl.business_date),
        revenue=str(pl.revenue),
        transaction_count=pl.transaction_count,
        cogs=str(pl.cogs),
        gross_profit=str(pl.gross_profit),
        gross_margin_percent=str(pl.gross_margin_percent),
        waste_amount=str(pl.waste_amount),
        opex={
            "total": str(pl.opex_total),
            "breakdown": {k: str(v) for k, v in pl.opex_breakdown.items()},
        },
        net_profit=str(pl.net_profit),
        net_margin_percent=str(pl.net_margin_percent),
        is_profitable=pl.net_profit > Decimal("0"),
    )


@router.get(
    "/daily-pnl",
    response_model=list[DailyPLResponse],
    summary="Get Daily P&L for Date Range",
)
async def get_daily_pnl_range(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    session: AsyncSession = Depends(get_db),
) -> list[DailyPLResponse]:
    """
    Get daily P&L statements for a range of dates.
    
    Useful for trend analysis and comparing daily performance.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    # Limit range to prevent too large queries
    days = (end_date - start_date).days + 1
    if days > 31:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 31 days. Use monthly report for longer periods.",
        )
    
    service = PLService(session)
    results = []
    
    current = start_date
    while current <= end_date:
        pl = await service.get_daily_pl(current)
        
        results.append(DailyPLResponse(
            business_date=str(pl.business_date),
            revenue=str(pl.revenue),
            transaction_count=pl.transaction_count,
            cogs=str(pl.cogs),
            gross_profit=str(pl.gross_profit),
            gross_margin_percent=str(pl.gross_margin_percent),
            waste_amount=str(pl.waste_amount),
            opex={
                "total": str(pl.opex_total),
                "breakdown": {k: str(v) for k, v in pl.opex_breakdown.items()},
            },
            net_profit=str(pl.net_profit),
            net_margin_percent=str(pl.net_margin_percent),
            is_profitable=pl.net_profit > Decimal("0"),
        ))
        
        current = date(
            current.year,
            current.month,
            current.day + 1 if current.day < 28 else 1,
        ) if current.day < 28 else _next_day(current)
    
    return results


def _next_day(d: date) -> date:
    """Get next day, handling month/year boundaries."""
    from datetime import timedelta
    return d + timedelta(days=1)


# ============================================================================
# Monthly P&L Endpoints
# ============================================================================

@router.get(
    "/monthly-pnl/{year}/{month}",
    response_model=MonthlyPLResponse,
    summary="Get Monthly P&L",
)
async def get_monthly_pnl(
    year: int,
    month: int,
    session: AsyncSession = Depends(get_db),
) -> MonthlyPLResponse:
    """
    Get Profit & Loss summary for an entire month.
    
    Includes:
    - Total revenue, COGS, gross profit
    - OPEX breakdown by category
    - Net profit
    - Daily averages
    """
    if not (1 <= month <= 12):
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12",
        )
    
    service = PLService(session)
    pl = await service.get_monthly_pl(year, month)
    
    return MonthlyPLResponse(
        year=pl.year,
        month=pl.month,
        days_in_month=pl.days_in_month,
        revenue=str(pl.revenue),
        transaction_count=pl.transaction_count,
        cogs=str(pl.cogs),
        gross_profit=str(pl.gross_profit),
        gross_margin_percent=str(pl.gross_margin_percent),
        waste_amount=str(pl.waste_amount),
        opex_total=str(pl.opex_total),
        opex_breakdown={k: str(v) for k, v in pl.opex_breakdown.items()},
        net_profit=str(pl.net_profit),
        net_margin_percent=str(pl.net_margin_percent),
        avg_daily_revenue=str(pl.avg_daily_revenue.quantize(Decimal("0.01"))),
        avg_daily_cogs=str(pl.avg_daily_cogs.quantize(Decimal("0.01"))),
        avg_daily_opex=str(pl.avg_daily_opex.quantize(Decimal("0.01"))),
        avg_daily_net_profit=str(pl.avg_daily_net_profit.quantize(Decimal("0.01"))),
        is_profitable=pl.net_profit > Decimal("0"),
    )


# ============================================================================
# Range P&L Endpoints
# ============================================================================

@router.get(
    "/pnl-range",
    response_model=PLRangeResponse,
    summary="Get P&L for Date Range",
)
async def get_pnl_range(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    session: AsyncSession = Depends(get_db),
) -> PLRangeResponse:
    """
    Get P&L summary for a custom date range.
    
    Useful for:
    - Week-over-week comparisons
    - Custom reporting periods
    - Quarter analysis
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    service = PLService(session)
    
    try:
        pl = await service.get_pl_range(start_date, end_date)
        
        return PLRangeResponse(
            start_date=str(pl.start_date),
            end_date=str(pl.end_date),
            days=pl.days,
            revenue=str(pl.revenue),
            cogs=str(pl.cogs),
            gross_profit=str(pl.gross_profit),
            gross_margin_percent=str(pl.gross_margin_percent),
            waste_amount=str(pl.waste_amount),
            opex_total=str(pl.opex_total),
            net_profit=str(pl.net_profit),
            net_margin_percent=str(pl.net_margin_percent),
            is_profitable=pl.net_profit > Decimal("0"),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================================
# Summary Endpoints
# ============================================================================

@router.get(
    "/today",
    response_model=DailyPLResponse,
    summary="Get Today's P&L",
)
async def get_today_pnl(
    session: AsyncSession = Depends(get_db),
) -> DailyPLResponse:
    """
    Get P&L for today's business date.
    
    Uses the Almaty timezone (UTC+5) with 06:00 cutoff.
    """
    from app.utils.timezone import get_business_date
    
    today = get_business_date()
    service = PLService(session)
    pl = await service.get_daily_pl(today)
    
    return DailyPLResponse(
        business_date=str(pl.business_date),
        revenue=str(pl.revenue),
        transaction_count=pl.transaction_count,
        cogs=str(pl.cogs),
        gross_profit=str(pl.gross_profit),
        gross_margin_percent=str(pl.gross_margin_percent),
        waste_amount=str(pl.waste_amount),
        opex={
            "total": str(pl.opex_total),
            "breakdown": {k: str(v) for k, v in pl.opex_breakdown.items()},
        },
        net_profit=str(pl.net_profit),
        net_margin_percent=str(pl.net_margin_percent),
        is_profitable=pl.net_profit > Decimal("0"),
    )


# ============================================================================
# Phase 4: Product Profitability Endpoints
# ============================================================================

class ProductProfitResponse(BaseModel):
    """Product profitability item."""
    product_id: str
    product_name: str
    quantity_sold: int
    revenue: str
    cogs: str
    profit: str
    margin_percent: str


class ProductProfitabilityResponse(BaseModel):
    """Product profitability report response."""
    business_date: str
    products: list[ProductProfitResponse]
    total_revenue: str
    total_cogs: str
    total_profit: str
    avg_margin_percent: str


@router.get(
    "/product-profitability/{business_date}",
    response_model=ProductProfitabilityResponse,
    summary="Get Product Profitability",
)
async def get_product_profitability(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> ProductProfitabilityResponse:
    """
    Get profitability per product for a business date.
    
    Shows:
    - Revenue per product
    - COGS per product (estimated from sale total_cost)
    - Profit and margin per product
    - Sorted by profit (highest first)
    """
    from app.services.analytics import AnalyticsService
    
    service = AnalyticsService(session)
    report = await service.get_product_profitability(business_date)
    
    return ProductProfitabilityResponse(
        business_date=str(report.business_date),
        products=[
            ProductProfitResponse(
                product_id=str(p.product_id),
                product_name=p.product_name,
                quantity_sold=p.quantity_sold,
                revenue=str(p.revenue),
                cogs=str(p.cogs),
                profit=str(p.profit),
                margin_percent=str(p.margin_percent),
            )
            for p in report.products
        ],
        total_revenue=str(report.total_revenue),
        total_cogs=str(report.total_cogs),
        total_profit=str(report.total_profit),
        avg_margin_percent=str(report.avg_margin_percent),
    )


# ============================================================================
# Phase 4: Inventory Analytics Endpoints
# ============================================================================

class IngredientStockResponse(BaseModel):
    """Ingredient stock status."""
    ingredient_id: str
    ingredient_name: str
    unit: str
    current_stock: str
    current_wac: str
    total_value: str
    is_low_stock: bool
    is_negative: bool


class InventoryStatusResponse(BaseModel):
    """Inventory status response."""
    as_of_date: str
    ingredients: list[IngredientStockResponse]
    total_value: str
    low_stock_count: int
    negative_stock_count: int


@router.get(
    "/inventory-status",
    response_model=InventoryStatusResponse,
    summary="Get Inventory Status",
)
async def get_inventory_status(
    low_stock_threshold: Decimal = Query(
        Decimal("20"),
        description="Threshold for low stock warning",
    ),
    session: AsyncSession = Depends(get_db),
) -> InventoryStatusResponse:
    """
    Get current inventory status for all ingredients.
    
    Shows:
    - Current stock (SUM of inventory_ledger)
    - Current WAC (latest weighted average cost)
    - Total value (stock × WAC)
    - Low stock alerts
    - Negative stock warnings
    
    Sorted by: Negative first, then low stock, then alphabetically.
    """
    from app.services.analytics import AnalyticsService
    
    service = AnalyticsService(session)
    report = await service.get_inventory_status(low_stock_threshold)
    
    return InventoryStatusResponse(
        as_of_date=str(report.as_of_date),
        ingredients=[
            IngredientStockResponse(
                ingredient_id=str(i.ingredient_id),
                ingredient_name=i.ingredient_name,
                unit=i.unit,
                current_stock=str(i.current_stock),
                current_wac=str(i.current_wac),
                total_value=str(i.total_value),
                is_low_stock=i.is_low_stock,
                is_negative=i.is_negative,
            )
            for i in report.ingredients
        ],
        total_value=str(report.total_value),
        low_stock_count=report.low_stock_count,
        negative_stock_count=report.negative_stock_count,
    )


# ============================================================================
# Phase 4: Dashboard Summary Endpoint
# ============================================================================

class DashboardResponse(BaseModel):
    """Dashboard summary response."""
    business_date: str
    revenue: str
    cogs: str
    gross_profit: str
    gross_margin_percent: str
    opex: str
    opex_breakdown: dict[str, str]
    net_profit: str
    net_margin_percent: str
    is_profitable: bool
    transaction_count: int


@router.get(
    "/dashboard-today",
    response_model=DashboardResponse,
    summary="Get Today's Dashboard Summary",
)
async def get_dashboard_today(
    session: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """
    Get dashboard summary for today's business date.
    
    Single endpoint returning all key metrics:
    - Revenue, COGS, Gross Profit
    - OPEX, Net Profit
    - Margins and profitability status
    
    Uses Almaty timezone (UTC+5) with 06:00 cutoff.
    """
    from app.services.analytics import AnalyticsService
    
    service = AnalyticsService(session)
    summary = await service.get_dashboard_summary()
    
    return DashboardResponse(
        business_date=str(summary.business_date),
        revenue=str(summary.revenue),
        cogs=str(summary.cogs),
        gross_profit=str(summary.gross_profit),
        gross_margin_percent=str(summary.gross_margin_percent),
        opex=str(summary.opex),
        opex_breakdown={k: str(v) for k, v in summary.opex_breakdown.items()},
        net_profit=str(summary.net_profit),
        net_margin_percent=str(summary.net_margin_percent),
        is_profitable=summary.is_profitable,
        transaction_count=summary.transaction_count,
    )


@router.get(
    "/dashboard/{business_date}",
    response_model=DashboardResponse,
    summary="Get Dashboard Summary for Date",
)
async def get_dashboard_for_date(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """
    Get dashboard summary for a specific business date.
    """
    from app.services.analytics import AnalyticsService
    
    service = AnalyticsService(session)
    summary = await service.get_dashboard_summary(business_date)
    
    return DashboardResponse(
        business_date=str(summary.business_date),
        revenue=str(summary.revenue),
        cogs=str(summary.cogs),
        gross_profit=str(summary.gross_profit),
        gross_margin_percent=str(summary.gross_margin_percent),
        opex=str(summary.opex),
        opex_breakdown={k: str(v) for k, v in summary.opex_breakdown.items()},
        net_profit=str(summary.net_profit),
        net_margin_percent=str(summary.net_margin_percent),
        is_profitable=summary.is_profitable,
        transaction_count=summary.transaction_count,
    )



# ============================================================================
# Phase 4: Audit Trail Endpoints

# ============================================================================

class AuditEntryResponse(BaseModel):
    """Audit trail entry."""
    id: str
    event_type: str
    change_amount: str
    unit_cost: str | None
    weighted_average_cost: str
    cost_snapshot: str
    negative_stock: bool
    reason: str | None
    business_date: str
    created_at: str
    running_balance: str


class AuditTrailResponse(BaseModel):
    """Audit trail response."""
    ingredient_id: str
    ingredient_name: str
    unit: str
    start_date: str
    end_date: str
    entries: list[AuditEntryResponse]
    starting_balance: str
    ending_balance: str


@router.get(
    "/audit/{ingredient_id}",
    response_model=AuditTrailResponse,
    summary="Get Ingredient Audit Trail",
)
async def get_audit_trail(
    ingredient_id: str,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    session: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Get complete audit trail for an ingredient.
    
    Shows all inventory movements with:
    - Event type (SUPPLY, SALE, CORRECTION, ADJUSTMENT)
    - Quantity changes
    - Costs and prices
    - Running balance
    
    Essential for traceability and compliance.
    """
    from uuid import UUID
    from app.services.analytics import AnalyticsService
    
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    try:
        ingredient_uuid = UUID(ingredient_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid ingredient_id format",
        )
    
    service = AnalyticsService(session)
    
    try:
        report = await service.get_audit_trail(ingredient_uuid, start_date, end_date)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    
    return AuditTrailResponse(
        ingredient_id=str(report.ingredient_id),
        ingredient_name=report.ingredient_name,
        unit=report.unit,
        start_date=str(report.start_date),
        end_date=str(report.end_date),
        entries=[
            AuditEntryResponse(
                id=str(e.id),
                event_type=e.event_type,
                change_amount=str(e.change_amount),
                unit_cost=str(e.unit_cost) if e.unit_cost is not None else None,
                weighted_average_cost=str(e.weighted_average_cost),
                cost_snapshot=str(e.cost_snapshot),
                negative_stock=e.negative_stock,
                reason=e.reason,
                business_date=str(e.business_date),
                created_at=e.created_at,
                running_balance=str(e.running_balance),
            )
            for e in report.entries
        ],
        starting_balance=str(report.starting_balance),
        ending_balance=str(report.ending_balance),
    )


# ============================================================================
# Phase 6.2: Product Sales Analytics Endpoints
# ============================================================================

class TopProductItem(BaseModel):
    """Top product item."""
    rank: int
    product_id: str
    product_name: str
    pos_code: int | None
    quantity_sold: int
    revenue: str
    cogs: str
    profit: str
    margin_percent: str
    share_of_revenue: str


class TopProductsResponse(BaseModel):
    """Top products response."""
    business_date: str | None
    start_date: str
    end_date: str
    total_revenue: str
    total_quantity: int
    products: list[TopProductItem]


@router.get(
    "/product-sales/top",
    response_model=TopProductsResponse,
    summary="Get Top Products by Sales",
)
async def get_top_products(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Number of products to return"),
    sort_by: str = Query("revenue", description="Sort by: revenue, quantity, profit, margin"),
    session: AsyncSession = Depends(get_db),
) -> TopProductsResponse:
    """
    Get top selling products for a date range.
    
    **Sortable by:**
    - revenue (default) - highest sales amount
    - quantity - most units sold
    - profit - highest profit (revenue - COGS)
    - margin - highest margin %
    
    **Example:**
    ```
    GET /reports/product-sales/top?start_date=2026-02-01&end_date=2026-02-03&limit=5
    ```
    """
    from sqlalchemy import func, desc
    from app.models import Sale, Product
    from app.models.sale import SaleItem
    
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    if sort_by not in ["revenue", "quantity", "profit", "margin"]:
        raise HTTPException(
            status_code=400,
            detail="sort_by must be one of: revenue, quantity, profit, margin",
        )
    
    # Query sales with items for the period
    from sqlalchemy import select
    from app.models import Sale, Product, SaleItem
    
    query = (
        select(Sale, SaleItem, Product)
        .join(SaleItem, Sale.id == SaleItem.sale_id)
        .join(Product, SaleItem.product_id == Product.id)
        .where(Sale.business_date >= start_date)
        # .where(Sale.business_date <= end_date) # Fixed: verify end_date inclusion
    )
    if end_date:
        query = query.where(Sale.business_date <= end_date)
        
    result = await session.execute(query)
    rows = result.all()
    
    # Aggregate data by product
    product_stats = {}
    total_revenue = Decimal("0")
    total_quantity = 0
    
    for sale, item, product in rows:
        pid = str(product.id)
        if pid not in product_stats:
            product_stats[pid] = {
                "product_id": pid,
                "product_name": product.name,
                "pos_code": product.pos_code,
                "quantity_sold": 0,
                "revenue": Decimal("0"),
                "cogs": Decimal("0")
            }
        
        # Distribute COGS based on revenue share in the sale
        # This respects Law 3 (Sale.total_cost is the truth)
        sale_rev = sale.total_amount
        sale_cogs = sale.total_cost
        item_rev = item.line_total
        
        if sale_rev > 0:
            # Proportional COGS
            item_cogs = (item_rev / sale_rev) * sale_cogs
        else:
            item_cogs = Decimal("0")
            
        product_stats[pid]["quantity_sold"] += item.quantity
        product_stats[pid]["revenue"] += item_rev
        product_stats[pid]["cogs"] += item_cogs
        
        total_revenue += item_rev
        total_quantity += item.quantity
        
    # Convert to list
    products_data = []
    for p in product_stats.values():
        rev = p["revenue"]
        cogs = p["cogs"]
        profit = rev - cogs
        margin = (profit / rev * 100).quantize(Decimal("0.1")) if rev > 0 else Decimal("0")
        
        p["revenue"] = rev
        p["cogs"] = cogs
        p["profit"] = profit
        p["margin_percent"] = margin
        products_data.append(p)
    
    # Sort
    sort_key = {
        "revenue": lambda x: x["revenue"],
        "quantity": lambda x: x["quantity_sold"],
        "profit": lambda x: x["profit"],
        "margin": lambda x: x["margin_percent"],
    }[sort_by]
    
    products_data.sort(key=sort_key, reverse=True)
    products_data = products_data[:limit]
    
    # Add rank and share
    result_products = []
    for i, p in enumerate(products_data, 1):
        share = (p["revenue"] / total_revenue * 100).quantize(Decimal("0.1")) if total_revenue > 0 else Decimal("0")
        result_products.append(TopProductItem(
            rank=i,
            product_id=p["product_id"],
            product_name=p["product_name"],
            pos_code=p["pos_code"],
            quantity_sold=p["quantity_sold"],
            revenue=str(p["revenue"].quantize(Decimal("0.01"))),
            cogs=str(p["cogs"].quantize(Decimal("0.01"))),
            profit=str(p["profit"].quantize(Decimal("0.01"))),
            margin_percent=str(p["margin_percent"]),
            share_of_revenue=str(share),
        ))
    
    return TopProductsResponse(
        business_date=None,
        start_date=str(start_date),
        end_date=str(end_date),
        total_revenue=str(total_revenue),
        total_quantity=total_quantity,
        products=result_products,
    )


class SalesTrendItem(BaseModel):
    """Daily sales trend item."""
    business_date: str
    revenue: str
    cogs: str
    gross_profit: str
    margin_percent: str
    transaction_count: int
    items_sold: int


class SalesTrendResponse(BaseModel):
    """Sales trend response."""
    start_date: str
    end_date: str
    days: int
    trend: list[SalesTrendItem]
    avg_daily_revenue: str
    avg_daily_profit: str
    best_day: str | None
    worst_day: str | None


@router.get(
    "/product-sales/trend",
    response_model=SalesTrendResponse,
    summary="Get Sales Trend Over Time",
)
async def get_sales_trend(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    session: AsyncSession = Depends(get_db),
) -> SalesTrendResponse:
    """
    Get daily sales trend for a date range.
    
    **Returns:**
    - Daily revenue, COGS, profit
    - Transaction counts
    - Best and worst performing days
    
    **Use for:**
    - Line charts of revenue over time
    - Week-over-week comparisons
    - Identifying patterns
    
    **Example:**
    ```
    GET /reports/product-sales/trend?start_date=2026-02-01&end_date=2026-02-07
    ```
    """
    from datetime import timedelta
    from sqlalchemy import func, select
    from app.models import Sale
    from app.models.sale import SaleItem
    
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    days = (end_date - start_date).days + 1
    if days > 90:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 90 days",
        )
    
    trend_data = []
    total_revenue = Decimal("0")
    total_profit = Decimal("0")
    best_day = None
    worst_day = None
    best_revenue = Decimal("0")
    worst_revenue = None
    
    current = start_date
    while current <= end_date:
        # Get daily sales and COGS
        query = (
            select(
                func.count(Sale.id).label("tx_count"),
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
                func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
            )
            .where(Sale.business_date == current)
        )
        result = await session.execute(query)
        row = result.one()
        
        tx_count = row.tx_count or 0
        revenue = Decimal(str(row.revenue))
        cogs = Decimal(str(row.cogs))
        
        # Get items sold
        items_query = (
            select(func.sum(SaleItem.quantity))
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.business_date == current)
        )
        items_result = await session.execute(items_query)
        items_sold = items_result.scalar() or 0
        
        gross_profit = revenue - cogs
        margin = (gross_profit / revenue * 100).quantize(Decimal("0.1")) if revenue > 0 else Decimal("0")
        
        trend_data.append(SalesTrendItem(
            business_date=str(current),
            revenue=str(revenue),
            cogs=str(cogs),
            gross_profit=str(gross_profit),
            margin_percent=str(margin),
            transaction_count=tx_count,
            items_sold=int(items_sold),
        ))
        
        total_revenue += revenue
        total_profit += gross_profit
        
        # Track best/worst
        if revenue > best_revenue:
            best_revenue = revenue
            best_day = str(current)
        
        if worst_revenue is None or (revenue < worst_revenue and revenue > 0):
            worst_revenue = revenue
            worst_day = str(current)
        
        current += timedelta(days=1)
    
    avg_daily_revenue = (total_revenue / Decimal(str(days))).quantize(Decimal("0.01"))
    avg_daily_profit = (total_profit / Decimal(str(days))).quantize(Decimal("0.01"))
    
    return SalesTrendResponse(
        start_date=str(start_date),
        end_date=str(end_date),
        days=days,
        trend=trend_data,
        avg_daily_revenue=str(avg_daily_revenue),
        avg_daily_profit=str(avg_daily_profit),
        best_day=best_day,
        worst_day=worst_day,
    )


# ============================================================================
# Period-based Sales Trend Endpoints (Day, Week, Month, Custom)
# ============================================================================

@router.get(
    "/sales/today",
    response_model=SalesTrendItem,
    summary="Get Today's Sales Summary",
)
async def get_sales_today(
    session: AsyncSession = Depends(get_db),
) -> SalesTrendItem:
    """
    Get sales summary for today (Almaty business date).
    
    Uses the 06:00 AM cutoff for business date.
    """
    from app.utils.timezone import get_business_date
    from datetime import timedelta
    from sqlalchemy import func, select
    from app.models import Sale
    from app.models.sale import SaleItem
    
    today = get_business_date()
    
    # Get daily sales
    # Get daily sales and COGS
    query = (
        select(
            func.count(Sale.id).label("tx_count"),
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
            func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
        )
        .where(Sale.business_date == today)
    )
    result = await session.execute(query)
    row = result.one()
    
    tx_count = row.tx_count or 0
    revenue = Decimal(str(row.revenue))
    cogs = Decimal(str(row.cogs))
    
    # Get items sold
    items_query = (
        select(func.sum(SaleItem.quantity))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.business_date == today)
    )
    items_result = await session.execute(items_query)
    items_sold = items_result.scalar() or 0
    
    # Calculate profit
    gross_profit = revenue - cogs
    margin = (gross_profit / revenue * 100).quantize(Decimal("0.1")) if revenue > 0 else Decimal("0")
    
    return SalesTrendItem(
        business_date=str(today),
        revenue=str(revenue),
        cogs=str(cogs),
        gross_profit=str(gross_profit),
        margin_percent=str(margin),
        transaction_count=tx_count,
        items_sold=int(items_sold),
    )


class PeriodSummaryResponse(BaseModel):
    """Period summary with comparison."""
    period_name: str  # "today", "week", "month", "custom"
    start_date: str
    end_date: str
    days: int
    
    # Current period
    revenue: str
    cogs: str
    gross_profit: str
    gross_margin_percent: str
    items_sold: int
    transaction_count: int
    avg_daily_revenue: str
    
    # Comparison with previous period
    prev_revenue: str | None
    revenue_change_percent: str | None
    revenue_trend: str | None  # "up", "down", "stable"
    
    # Best/worst
    best_day: str | None
    best_day_revenue: str | None
    worst_day: str | None
    worst_day_revenue: str | None
    
    # Financial metrics
    waste_amount: str
    opex_total: str
    net_profit: str
    net_margin_percent: str


@router.get(
    "/sales/week",
    response_model=PeriodSummaryResponse,
    summary="Get This Week's Sales",
)
async def get_sales_week(
    date: date = Query(None, description="Date in target week (default: current business date)"),
    session: AsyncSession = Depends(get_db),
) -> PeriodSummaryResponse:
    """
    Get sales summary for current week (Mon-Sun).
    
    Includes comparison with previous week.
    """
    from app.utils.timezone import get_business_date
    from datetime import timedelta
    
    today = get_business_date()
    target_date = date or today
    
    # Calculate week bounds (Monday to Sunday)
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    # Previous week
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_start - timedelta(days=1)
    
    actual_end = min(week_end, today) if week_start <= today else week_end
    current = await _get_period_summary(session, week_start, actual_end)
    previous = await _get_period_summary(session, prev_week_start, prev_week_end)
    
    # Calculate change
    revenue_change = None
    trend = None
    if previous["revenue"] > 0:
        change = ((current["revenue"] - previous["revenue"]) / previous["revenue"] * 100)
        revenue_change = str(change.quantize(Decimal("0.1")))
        trend = "up" if change > 0 else "down" if change < 0 else "stable"
    
    return PeriodSummaryResponse(
        period_name="week",
        start_date=str(week_start),
        end_date=str(actual_end),
        days=current["days"],
        revenue=str(current["revenue"]),
        cogs=str(current["cogs"]),
        gross_profit=str(current["gross_profit"]),
        gross_margin_percent=str(current["margin"]),
        items_sold=current["items_sold"],
        transaction_count=current["tx_count"],
        avg_daily_revenue=str(current["avg_revenue"]),
        prev_revenue=str(previous["revenue"]) if previous["revenue"] > 0 else None,
        revenue_change_percent=revenue_change,
        revenue_trend=trend,
        best_day=current["best_day"],
        best_day_revenue=str(current["best_revenue"]) if current["best_revenue"] else None,
        worst_day=current["worst_day"],
        worst_day_revenue=str(current["worst_revenue"]) if current["worst_revenue"] else None,
        waste_amount=str(current["waste_amount"]),
        opex_total=str(current["opex_total"]),
        net_profit=str(current["net_profit"]),
        net_margin_percent=str(current["net_margin_percent"]),
    )


@router.get(
    "/sales/month",
    response_model=PeriodSummaryResponse,
    summary="Get This Month's Sales",
)
async def get_sales_month(
    year: int = Query(None, description="Year (default: current)"),
    month: int = Query(None, description="Month 1-12 (default: current)"),
    session: AsyncSession = Depends(get_db),
) -> PeriodSummaryResponse:
    """
    Get sales summary for a month.
    
    Includes comparison with previous month.
    """
    from app.utils.timezone import get_business_date
    from datetime import timedelta
    import calendar
    
    today = get_business_date()
    
    # Use provided year/month or current
    target_year = year or today.year
    target_month = month or today.month
    
    # Calculate month bounds
    month_start = date(target_year, target_month, 1)
    days_in_month = calendar.monthrange(target_year, target_month)[1]
    month_end = date(target_year, target_month, days_in_month)
    
    # Previous month
    if target_month == 1:
        prev_year, prev_month = target_year - 1, 12
    else:
        prev_year, prev_month = target_year, target_month - 1
    
    prev_month_start = date(prev_year, prev_month, 1)
    prev_days_in_month = calendar.monthrange(prev_year, prev_month)[1]
    prev_month_end = date(prev_year, prev_month, prev_days_in_month)
    
    # Get data up to today if current month
    actual_end = min(month_end, today) if target_year == today.year and target_month == today.month else month_end
    
    current = await _get_period_summary(session, month_start, actual_end)
    previous = await _get_period_summary(session, prev_month_start, prev_month_end)
    
    # Calculate change
    revenue_change = None
    trend = None
    if previous["revenue"] > 0:
        change = ((current["revenue"] - previous["revenue"]) / previous["revenue"] * 100)
        revenue_change = str(change.quantize(Decimal("0.1")))
        trend = "up" if change > 0 else "down" if change < 0 else "stable"
    
    return PeriodSummaryResponse(
        period_name="month",
        start_date=str(month_start),
        end_date=str(actual_end),
        days=current["days"],
        revenue=str(current["revenue"]),
        cogs=str(current["cogs"]),
        gross_profit=str(current["gross_profit"]),
        gross_margin_percent=str(current["margin"]),
        items_sold=current["items_sold"],
        transaction_count=current["tx_count"],
        avg_daily_revenue=str(current["avg_revenue"]),
        prev_revenue=str(previous["revenue"]) if previous["revenue"] > 0 else None,
        revenue_change_percent=revenue_change,
        revenue_trend=trend,
        best_day=current["best_day"],
        best_day_revenue=str(current["best_revenue"]) if current["best_revenue"] else None,
        worst_day=current["worst_day"],
        worst_day_revenue=str(current["worst_revenue"]) if current["worst_revenue"] else None,
        waste_amount=str(current["waste_amount"]),
        opex_total=str(current["opex_total"]),
        net_profit=str(current["net_profit"]),
        net_margin_percent=str(current["net_margin_percent"]),
    )


@router.get(
    "/sales/period",
    response_model=PeriodSummaryResponse,
    summary="Get Custom Period Sales",
)
async def get_sales_period(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    session: AsyncSession = Depends(get_db),
) -> PeriodSummaryResponse:
    """
    Get sales summary for a custom date range.
    
    Includes comparison with equal previous period.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )
    
    from datetime import timedelta
    
    days = (end_date - start_date).days + 1
    if days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 365 days",
        )
    
    # Previous period of same length
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    
    current = await _get_period_summary(session, start_date, end_date)
    previous = await _get_period_summary(session, prev_start, prev_end)
    
    # Calculate change
    revenue_change = None
    trend = None
    if previous["revenue"] > 0:
        change = ((current["revenue"] - previous["revenue"]) / previous["revenue"] * 100)
        revenue_change = str(change.quantize(Decimal("0.1")))
        trend = "up" if change > 0 else "down" if change < 0 else "stable"
    
    return PeriodSummaryResponse(
        period_name="custom",
        start_date=str(start_date),
        end_date=str(end_date),
        days=current["days"],
        revenue=str(current["revenue"]),
        cogs=str(current["cogs"]),
        gross_profit=str(current["gross_profit"]),
        gross_margin_percent=str(current["margin"]),
        items_sold=current["items_sold"],
        transaction_count=current["tx_count"],
        avg_daily_revenue=str(current["avg_revenue"]),
        prev_revenue=str(previous["revenue"]) if previous["revenue"] > 0 else None,
        revenue_change_percent=revenue_change,
        revenue_trend=trend,
        best_day=current["best_day"],
        best_day_revenue=str(current["best_revenue"]) if current["best_revenue"] else None,
        worst_day=current["worst_day"],
        worst_day_revenue=str(current["worst_revenue"]) if current["worst_revenue"] else None,
        waste_amount=str(current["waste_amount"]),
        opex_total=str(current["opex_total"]),
        net_profit=str(current["net_profit"]),
        net_margin_percent=str(current["net_margin_percent"]),
    )


async def _get_period_summary(session: AsyncSession, start: date, end: date) -> dict:
    """Helper function to calculate period summary."""
    from datetime import timedelta
    from sqlalchemy import func, select
    from app.models import Sale
    from app.models.sale import SaleItem
    from app.models.inventory_ledger import InventoryLedger, InventoryEventType
    from app.models.finance_ledger import FinanceLedger
    
    days = (end - start).days + 1
    
    # 1. Query all sales in the range grouped by business_date
    sales_query = (
        select(
            Sale.business_date,
            func.count(Sale.id).label("tx_count"),
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
            func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
        )
        .where(Sale.business_date >= start)
        .where(Sale.business_date <= end)
        .group_by(Sale.business_date)
    )
    sales_result = await session.execute(sales_query)
    sales_by_date = {row.business_date: row for row in sales_result.all()}
    
    # 2. Query all sale items in the range grouped by business_date
    items_query = (
        select(
            Sale.business_date,
            func.coalesce(func.sum(SaleItem.quantity), Decimal("0")).label("items")
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.business_date >= start)
        .where(Sale.business_date <= end)
        .group_by(Sale.business_date)
    )
    items_result = await session.execute(items_query)
    items_by_date = {row.business_date: int(row.items) for row in items_result.all()}
    
    # 3. Query waste in range
    waste_result = await session.execute(
        select(func.coalesce(func.sum(InventoryLedger.cost_snapshot), Decimal("0")))
        .where(InventoryLedger.event_type == InventoryEventType.WASTE.value)
        .where(InventoryLedger.business_date >= start)
        .where(InventoryLedger.business_date <= end)
    )
    total_waste = Decimal(str(waste_result.scalar() or "0"))
    
    # 4. Query OPEX in range
    opex_result = await session.execute(
        select(func.coalesce(func.sum(FinanceLedger.amount), Decimal("0")))
        .where(FinanceLedger.business_date >= start)
        .where(FinanceLedger.business_date <= end)
    )
    total_opex = Decimal(str(opex_result.scalar() or "0"))
    
    total_revenue = Decimal("0")
    total_cogs = Decimal("0")
    total_items = 0
    total_tx = 0
    best_day = None
    best_revenue = Decimal("0")
    worst_day = None
    worst_revenue = None
    
    current = start
    while current <= end:
        row = sales_by_date.get(current)
        if row:
            tx_count = row.tx_count or 0
            revenue = Decimal(str(row.revenue))
            cogs = Decimal(str(row.cogs))
        else:
            tx_count = 0
            revenue = Decimal("0")
            cogs = Decimal("0")
            
        items = items_by_date.get(current, 0)
        
        total_revenue += revenue
        total_cogs += cogs
        total_items += items
        total_tx += tx_count
        
        # Track best/worst
        if revenue > best_revenue:
            best_revenue = revenue
            best_day = str(current)
        
        if revenue > 0 and (worst_revenue is None or revenue < worst_revenue):
            worst_revenue = revenue
            worst_day = str(current)
            
        current += timedelta(days=1)
        
    gross_profit = total_revenue - total_cogs
    margin = (gross_profit / total_revenue * 100).quantize(Decimal("0.1")) if total_revenue > 0 else Decimal("0")
    avg_revenue = (total_revenue / Decimal(str(days))).quantize(Decimal("0.01")) if days > 0 else Decimal("0")
    
    net_profit = gross_profit - total_waste - total_opex
    net_margin = (net_profit / total_revenue * 100).quantize(Decimal("0.1")) if total_revenue > 0 else Decimal("0")
    
    return {
        "days": days,
        "revenue": total_revenue.quantize(Decimal("0.01")),
        "cogs": total_cogs.quantize(Decimal("0.01")),
        "gross_profit": gross_profit.quantize(Decimal("0.01")),
        "margin": margin,
        "items_sold": total_items,
        "tx_count": total_tx,
        "avg_revenue": avg_revenue,
        "best_day": best_day,
        "best_revenue": best_revenue.quantize(Decimal("0.01")) if best_revenue else None,
        "worst_day": worst_day,
        "worst_revenue": worst_revenue.quantize(Decimal("0.01")) if worst_revenue else None,
        "waste_amount": total_waste.quantize(Decimal("0.01")),
        "opex_total": total_opex.quantize(Decimal("0.01")),
        "net_profit": net_profit.quantize(Decimal("0.01")),
        "net_margin_percent": net_margin,
    }


# ============================================================================
# Phase 6.3: Product Cost Table
# ============================================================================

class ProductCostItemResponse(BaseModel):
    product_id: str
    product_name: str
    category: str | None
    serving_unit: str | None
    serving_size: str | None
    pos_code: int | None
    sale_price: str
    cost: str
    gross_margin: str
    gross_margin_percent: str


class ProductCostReportResponse(BaseModel):
    business_date: str
    products: list[ProductCostItemResponse]
    total_products: int
    avg_margin_percent: str


@router.get(
    "/product-costs",
    response_model=ProductCostReportResponse,
    summary="Get Theoretical Product Costs",
)
async def get_product_costs(
    session: AsyncSession = Depends(get_db),
) -> ProductCostReportResponse:
    """
    Get theoretical cost breakdown for all active products.

    Calculated using CURRENT weighted average cost of ingredients.
    Sorted by margin % (lowest first).
    """
    from app.services.analytics import AnalyticsService

    service = AnalyticsService(session)
    report = await service.get_product_costs()

    return ProductCostReportResponse(
        business_date=str(report.business_date),
        products=[
            ProductCostItemResponse(
                product_id=str(i.product_id),
                product_name=i.product_name,
                category=i.category,
                serving_unit=i.serving_unit,
                serving_size=i.serving_size,
                pos_code=i.pos_code,
                sale_price=str(i.sale_price),
                cost=str(i.cost),
                gross_margin=str(i.gross_margin),
                gross_margin_percent=str(i.gross_margin_percent),
            )
            for i in report.products
        ],
        total_products=report.total_products,
        avg_margin_percent=str(report.avg_margin_percent),
    )


# ============================================================================
# Phase 6.4: COGS Variance Report (Actual vs Theoretical)
# ============================================================================

class IngredientVarianceItem(BaseModel):
    """Ingredient-level variance."""
    ingredient_id: str
    ingredient_name: str
    unit: str
    theoretical_qty: str
    actual_qty: str
    variance_qty: str
    theoretical_cost: str
    actual_cost: str
    variance_cost: str
    variance_percent: str

class ProductVarianceItem(BaseModel):
    """Product-level variance."""
    product_id: str
    product_name: str
    pos_code: int | None
    quantity_sold: int
    theoretical_cogs: str
    actual_cogs: str
    variance: str
    variance_percent: str

class COGSVarianceResponse(BaseModel):
    """COGS Variance Report response."""
    business_date: str

    # Overall summary
    theoretical_cogs_total: str
    actual_cogs_total: str
    variance_amount: str
    variance_percent: str
    status: str  # "✅ OK", "⚠️ WARNING", "🚨 CRITICAL"

    # Breakdowns
    product_variances: list[ProductVarianceItem]
    ingredient_variances: list[IngredientVarianceItem]

    # Metrics
    products_over_variance: int
    ingredients_over_variance: int
    acceptable_threshold: str

@router.get(
    "/cogs-variance/{business_date}",
    response_model=COGSVarianceResponse,
    summary="Get COGS Variance Report (Actual vs Theoretical)",
)
async def get_cogs_variance(
    business_date: date,
    threshold: Decimal = Query(Decimal("3.0"), description="Acceptable variance % (default 3%)"),
    session: AsyncSession = Depends(get_db),
) -> COGSVarianceResponse:
    """
    **COGS Accuracy Verification - Industry Standard Method**

    Compares Theoretical COGS (from recipes) vs Actual COGS (from inventory ledger).
    This is the gold standard method used by all major restaurant ERP systems.

    **Formula:**
    ```
    Theoretical COGS = SUM(recipe cost × quantity sold)
    Actual COGS = SUM(inventory_ledger.cost_snapshot WHERE event='SALE')
    Variance % = (Actual - Theoretical) / Theoretical × 100
    ```

    **Status Indicators:**
    - ✅ OK: Variance < 3% (system is accurate)
    - ⚠️ WARNING: Variance 3-5% (minor issues)
    - 🚨 CRITICAL: Variance > 5% (significant problems)

    **Use Cases:**
    - Verify recipe accuracy
    - Detect theft or waste
    - Validate inventory tracking
    - Audit COGS calculations

    **Industry Benchmarks:**
    - QSR (Quick Service): 1.5-3%
    - Fast Casual: 2-4%
    - Full Service: 3-5%

    **Example Response:**
    ```json
    {
      "variance_percent": "2.1",
      "status": "✅ OK",
      "theoretical_cogs_total": "5251.00",
      "actual_cogs_total": "5361.27",
      "variance_amount": "110.27"
    }
    ```
    """
    from sqlalchemy import select, func
    from app.models import Sale, Product, Recipe, InventoryLedger, Ingredient
    from app.models.sale import SaleItem
    from collections import defaultdict

    # ==========================================================================
    # STEP 1: Calculate Theoretical COGS (from recipes × sales)
    # ==========================================================================

    # Get all sales for the date with items
    sales_query = (
        select(Sale, SaleItem, Product)
        .join(SaleItem, Sale.id == SaleItem.sale_id)
        .join(Product, SaleItem.product_id == Product.id)
        .where(Sale.business_date == business_date)
    )
    sales_result = await session.execute(sales_query)
    sales_rows = sales_result.all()

    theoretical_by_product = {}
    theoretical_by_ingredient = defaultdict(lambda: {"qty": Decimal("0"), "cost": Decimal("0")})

    for sale, item, product in sales_rows:
        product_id = str(product.id)

        if product_id not in theoretical_by_product:
            theoretical_by_product[product_id] = {
                "product_id": product_id,
                "product_name": product.name,
                "pos_code": product.pos_code,
                "quantity_sold": 0,
                "theoretical_cogs": Decimal("0"),
            }

        theoretical_by_product[product_id]["quantity_sold"] += item.quantity

        # Get recipes for this product
        recipes_query = select(Recipe).where(Recipe.product_id == product.id)
        recipes_result = await session.execute(recipes_query)
        recipes = recipes_result.scalars().all()

        for recipe in recipes:
            # Calculate theoretical cost using current WAC
            ingredient_query = select(Ingredient).where(Ingredient.id == recipe.ingredient_id)
            ingredient_result = await session.execute(ingredient_query)
            ingredient = ingredient_result.scalar_one_or_none()

            if not ingredient:
                continue

            # Get current WAC from latest inventory ledger entry
            wac_query = (
                select(InventoryLedger.weighted_average_cost)
                .where(InventoryLedger.ingredient_id == recipe.ingredient_id)
                .where(InventoryLedger.business_date <= business_date)
                .order_by(InventoryLedger.business_date.desc(), InventoryLedger.created_at.desc())
                .limit(1)
            )
            wac_result = await session.execute(wac_query)
            wac = wac_result.scalar_one_or_none() or Decimal("0")

            # Theoretical cost for this recipe line
            recipe_cost = recipe.quantity * wac * item.quantity
            theoretical_by_product[product_id]["theoretical_cogs"] += recipe_cost

            # Track by ingredient
            ingredient_key = str(ingredient.id)
            theoretical_by_ingredient[ingredient_key]["id"] = ingredient_key
            theoretical_by_ingredient[ingredient_key]["name"] = ingredient.name
            theoretical_by_ingredient[ingredient_key]["unit"] = ingredient.unit
            theoretical_by_ingredient[ingredient_key]["qty"] += recipe.quantity * item.quantity
            theoretical_by_ingredient[ingredient_key]["cost"] += recipe_cost

    theoretical_cogs_total = sum(
        p["theoretical_cogs"] for p in theoretical_by_product.values()
    )

    # ==========================================================================
    # STEP 2: Calculate Actual COGS (from inventory_ledger)
    # ==========================================================================

    actual_query = (
        select(
            InventoryLedger.ingredient_id,
            Ingredient.name,
            Ingredient.unit,
            func.sum(InventoryLedger.change_amount).label("total_qty"),
            func.sum(InventoryLedger.cost_snapshot).label("total_cost"),
        )
        .join(Ingredient, InventoryLedger.ingredient_id == Ingredient.id)
        .where(InventoryLedger.business_date == business_date)
        .where(InventoryLedger.event_type == "SALE")
        .group_by(InventoryLedger.ingredient_id, Ingredient.name, Ingredient.unit)
    )
    actual_result = await session.execute(actual_query)
    actual_rows = actual_result.all()

    actual_by_ingredient = {}
    actual_cogs_total = Decimal("0")

    for row in actual_rows:
        ingredient_id = str(row.ingredient_id)
        qty = abs(Decimal(str(row.total_qty)))  # SALE is negative
        cost = abs(Decimal(str(row.total_cost)))  # SALE cost is negative

        actual_by_ingredient[ingredient_id] = {
            "id": ingredient_id,
            "name": row.name,
            "unit": row.unit,
            "qty": qty,
            "cost": cost,
        }
        actual_cogs_total += cost

    # Calculate actual COGS per product (proportional to theoretical)
    actual_by_product = {}
    for pid, pdata in theoretical_by_product.items():
        if theoretical_cogs_total > 0:
            proportion = pdata["theoretical_cogs"] / theoretical_cogs_total
            actual_cogs = actual_cogs_total * proportion
        else:
            actual_cogs = Decimal("0")

        actual_by_product[pid] = actual_cogs

    # ==========================================================================
    # STEP 3: Calculate Variances
    # ==========================================================================

    # Overall variance
    variance_amount = actual_cogs_total - theoretical_cogs_total
    variance_percent = (
        (variance_amount / theoretical_cogs_total * Decimal("100")).quantize(Decimal("0.01"))
        if theoretical_cogs_total > 0
        else Decimal("0")
    )

    # Status determination
    abs_variance = abs(variance_percent)
    if abs_variance < threshold:
        status = "✅ OK"
    elif abs_variance < Decimal("5.0"):
        status = "⚠️ WARNING"
    else:
        status = "🚨 CRITICAL"

    # Product-level variances
    product_variances = []
    products_over_variance = 0

    for pid, pdata in theoretical_by_product.items():
        theo = pdata["theoretical_cogs"]
        actual = actual_by_product.get(pid, Decimal("0"))
        var = actual - theo
        var_pct = (
            (var / theo * Decimal("100")).quantize(Decimal("0.01"))
            if theo > 0
            else Decimal("0")
        )

        if abs(var_pct) > threshold:
            products_over_variance += 1

        product_variances.append(ProductVarianceItem(
            product_id=pdata["product_id"],
            product_name=pdata["product_name"],
            pos_code=pdata["pos_code"],
            quantity_sold=pdata["quantity_sold"],
            theoretical_cogs=str(theo.quantize(Decimal("0.01"))),
            actual_cogs=str(actual.quantize(Decimal("0.01"))),
            variance=str(var.quantize(Decimal("0.01"))),
            variance_percent=str(var_pct),
        ))

    # Ingredient-level variances
    ingredient_variances = []
    ingredients_over_variance = 0

    all_ingredient_ids = set(theoretical_by_ingredient.keys()) | set(actual_by_ingredient.keys())

    for ing_id in all_ingredient_ids:
        theo_data = theoretical_by_ingredient.get(ing_id, {})
        actual_data = actual_by_ingredient.get(ing_id, {})

        theo_qty = theo_data.get("qty", Decimal("0"))
        actual_qty = actual_data.get("qty", Decimal("0"))
        theo_cost = theo_data.get("cost", Decimal("0"))
        actual_cost = actual_data.get("cost", Decimal("0"))

        name = theo_data.get("name") or actual_data.get("name", "Unknown")
        unit = theo_data.get("unit") or actual_data.get("unit", "")

        var_qty = actual_qty - theo_qty
        var_cost = actual_cost - theo_cost
        var_pct = (
            (var_cost / theo_cost * Decimal("100")).quantize(Decimal("0.01"))
            if theo_cost > 0
            else Decimal("0")
        )

        if abs(var_pct) > threshold:
            ingredients_over_variance += 1

        ingredient_variances.append(IngredientVarianceItem(
            ingredient_id=ing_id,
            ingredient_name=name,
            unit=unit,
            theoretical_qty=str(theo_qty.quantize(Decimal("0.01"))),
            actual_qty=str(actual_qty.quantize(Decimal("0.01"))),
            variance_qty=str(var_qty.quantize(Decimal("0.01"))),
            theoretical_cost=str(theo_cost.quantize(Decimal("0.01"))),
            actual_cost=str(actual_cost.quantize(Decimal("0.01"))),
            variance_cost=str(var_cost.quantize(Decimal("0.01"))),
            variance_percent=str(var_pct),
        ))

    # Sort by variance % (worst first)
    product_variances.sort(key=lambda x: abs(Decimal(x.variance_percent)), reverse=True)
    ingredient_variances.sort(key=lambda x: abs(Decimal(x.variance_percent)), reverse=True)

    return COGSVarianceResponse(
        business_date=str(business_date),
        theoretical_cogs_total=str(theoretical_cogs_total.quantize(Decimal("0.01"))),
        actual_cogs_total=str(actual_cogs_total.quantize(Decimal("0.01"))),
        variance_amount=str(variance_amount.quantize(Decimal("0.01"))),
        variance_percent=str(variance_percent),
        status=status,
        product_variances=product_variances,
        ingredient_variances=ingredient_variances,
        products_over_variance=products_over_variance,
        ingredients_over_variance=ingredients_over_variance,
        acceptable_threshold=str(threshold),
    )


@router.get(
    "/variance/{business_date}",
    summary="Variance Analysis (Theory vs Fact)",
)
async def get_variance_report(
    business_date: date,
    session: AsyncSession = Depends(get_db),
):
    """
    Get variance report comparing theoretical ingredient consumption (from recipes)
    with factual consumption (from inventory ledger) for a given business date.
    """
    service = AnalyticsService(session)
    report = await service.get_variance_report(business_date)
    return report

