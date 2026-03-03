"""
WENDRINK ERP - Sales API Endpoints

Sale creation and reporting.

LAWS ENFORCED:
- Law 3: Cost Snapshot Immutable
- Law 5: Negative Stock Allowed
- Law 7: Atomic Transactions
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.sale import SaleItemCreate, SaleRead
from app.services.sale import SaleItemInput, SaleService

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class SaleRequest(BaseModel):
    """Request to create a sale."""
    items: list[SaleItemCreate] = Field(..., min_length=1)
    business_date: date | None = Field(None, description="Business date (defaults to today)")


class SaleResponse(BaseModel):
    """Response from a sale operation."""
    id: str
    total_revenue: str
    total_cogs: str
    gross_profit: str
    gross_margin_percent: str
    item_count: int
    business_date: str
    warnings: list[str]
    message: str


class DailySummaryResponse(BaseModel):
    """Daily sales summary."""
    business_date: str
    total_revenue: str
    total_cogs: str
    gross_profit: str
    gross_margin_percent: str
    transaction_count: int


# ============================================================================
# Sale Endpoints
# ============================================================================

@router.post(
    "",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Sale",
)
async def create_sale(
    data: SaleRequest,
    session: AsyncSession = Depends(get_db),
) -> SaleResponse:
    """
    Create a sale with atomic COGS capture.
    
    This operation is ATOMIC:
    - All items are processed or none
    - Inventory is deducted for each ingredient in each product's recipe
    - COGS is captured at current WAC (immutable after this point)
    - Negative stock is allowed but flagged with warnings
    
    **IMPORTANT:**
    - Product prices are snapshotted at sale time
    - COGS is snapshotted at sale time and NEVER changes
    - Historical profit calculations remain stable
    """
    service = SaleService(session)
    
    # Convert request items to service input
    items = [
        SaleItemInput(
            product_id=item.product_id,
            quantity=item.quantity,
        )
        for item in data.items
    ]
    
    try:
        result = await service.create_sale(
            items=items,
            business_date=data.business_date,
        )
        
        await session.commit()
        
        # Invalidate cache — dashboard needs fresh data
        from app.utils.cache import invalidate_cache
        invalidate_cache()
        
        # Calculate margin
        margin = Decimal("0")
        if result.total_revenue > 0:
            margin = (result.gross_profit / result.total_revenue) * 100
        
        return SaleResponse(
            id=str(result.sale.id),
            total_revenue=str(result.total_revenue),
            total_cogs=str(result.total_cogs),
            gross_profit=str(result.gross_profit),
            gross_margin_percent=str(round(margin, 2)),
            item_count=len(result.items),
            business_date=str(result.sale.business_date),
            warnings=result.negative_stock_warnings,
            message="Sale completed successfully",
        )
        
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sale failed: {str(e)}",
        )


@router.get(
    "",
    response_model=list[SaleRead],
    summary="List Sales",
)
async def list_sales(
    session: AsyncSession = Depends(get_db),
    business_date: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list:
    """
    Get sales with optional filters.
    
    - Filter by business_date to see sales for a specific day
    - Results are ordered by most recent first
    """
    service = SaleService(session)
    sales = await service.get_sales(
        business_date=business_date,
        limit=limit,
        offset=offset,
    )
    
    return sales


@router.get(
    "/daily-summary",
    response_model=DailySummaryResponse,
    summary="Get Daily Sales Summary",
)
async def get_daily_summary(
    business_date: date,
    session: AsyncSession = Depends(get_db),
) -> DailySummaryResponse:
    """
    Get sales summary for a business date.
    
    Includes:
    - Total revenue
    - Total COGS
    - Gross profit
    - Gross margin percentage
    - Transaction count
    """
    service = SaleService(session)
    summary = await service.get_daily_summary(business_date)
    
    return DailySummaryResponse(
        business_date=str(summary["business_date"]),
        total_revenue=str(summary["total_revenue"]),
        total_cogs=str(summary["total_cogs"]),
        gross_profit=str(summary["gross_profit"]),
        gross_margin_percent=str(round(summary["gross_margin_percent"], 2)),
        transaction_count=summary["transaction_count"],
    )


@router.get(
    "/{sale_id}",
    response_model=SaleRead,
    summary="Get Sale",
)
async def get_sale(
    sale_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a sale by ID with all line items."""
    service = SaleService(session)
    sale = await service.get_sale(sale_id)
    
    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale {sale_id} not found",
        )
    
    return sale
