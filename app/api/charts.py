"""
WENDRINK ERP - Charts API Endpoints

Provides chart visualization endpoints for product sales analytics.
Follows Law 4: Almaty Business Date (06:00 cutoff).
"""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.charts import ProductSalesChartService
from app.utils.timezone import get_business_date


# === FastAPI Router ===
router = APIRouter()


# === Response Schemas ===
class ProductChartItem(BaseModel):
    """Single product data in chart response."""
    product: str = Field(..., description="Product name")
    quantity: int = Field(..., description="Quantity sold")
    revenue: str = Field(..., description="Revenue as string (Decimal)")
    percentage: str = Field(..., description="Percentage of total revenue")


class TopProductsChartResponse(BaseModel):
    """Response for top products chart endpoint."""
    status: str = Field(default="success")
    business_date: str = Field(..., description="Business date (YYYY-MM-DD)")
    bar_chart: Optional[str] = Field(None, description="Base64-encoded PNG bar chart")
    pie_chart: Optional[str] = Field(None, description="Base64-encoded PNG pie chart")
    data: list[ProductChartItem] = Field(default_factory=list, description="Product data")
    total: str = Field(..., description="Total revenue as string")


# === Endpoints ===
@router.get(
    "/product-sales/top",
    response_model=TopProductsChartResponse,
    summary="Get Top Products Chart",
    description="""
    Returns top products by quantity sold with bar and pie charts.
    
    **Charts returned:**
    - **bar_chart**: Horizontal bar chart showing quantity sold per product
    - **pie_chart**: Pie chart showing revenue distribution (top 10)
    
    **Business Date Logic (Law 4):**
    - If no date provided, uses current Almaty business date
    - Business day starts at 06:00 AM Almaty time
    - Sales from 00:00-05:59 count as previous day
    
    **Financial Precision (Law 2):**
    - All revenue values use Decimal precision
    - Percentages rounded to 1 decimal place
    """
)
async def get_top_products_chart(
    business_date: Optional[date] = Query(
        None,
        description="Business date (YYYY-MM-DD). Defaults to current Almaty business date."
    ),
    limit: int = Query(
        15,
        ge=1,
        le=50,
        description="Maximum number of products to include (1-50)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top products chart with bar and pie visualizations.
    
    Returns base64-encoded PNG charts for:
    - Bar chart: Product quantities sold
    - Pie chart: Revenue distribution (top 10)
    """
    # Law 4: Use Almaty business date if not provided
    if business_date is None:
        business_date = get_business_date(datetime.now(timezone.utc))
    
    try:
        result = await ProductSalesChartService.get_top_products(
            db=db,
            business_date=business_date,
            limit=limit
        )
        
        return TopProductsChartResponse(
            status="success",
            business_date=result["business_date"],
            bar_chart=result["bar_chart"],
            pie_chart=result["pie_chart"],
            data=[ProductChartItem(**item) for item in result["data"]],
            total=result["total"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate charts: {str(e)}"
        )


# === Sales Trend Response Schemas ===
class SalesTrendDataPoint(BaseModel):
    """Single data point in sales trend."""
    business_date: str = Field(..., description="Business date (YYYY-MM-DD)")
    revenue: str = Field(..., description="Daily revenue as string (Decimal)")
    cogs: str = Field(..., description="Daily COGS as string (Decimal)")
    gross_profit: str = Field(..., description="Daily gross profit as string")
    margin_percent: str = Field(..., description="Gross margin percentage")
    opex: str = Field(default="0.00", description="Daily OPEX")
    net_profit: str = Field(default="0.00", description="Daily Net Profit")


class SalesTrendSummary(BaseModel):
    """Summary statistics for sales trend."""
    total_revenue: str = Field(..., description="Total revenue for period")
    total_cogs: str = Field(..., description="Total COGS for period")
    total_gross_profit: str = Field(..., description="Total gross profit")
    total_opex: str = Field(default="0.00", description="Total OPEX")
    total_net_profit: str = Field(default="0.00", description="Total Net Profit")
    avg_daily_revenue: str = Field(..., description="Average daily revenue")
    days_count: int = Field(..., description="Number of days with sales")


class SalesTrendResponse(BaseModel):
    """Response for sales trend endpoint."""
    status: str = Field(default="success")
    start_date: str = Field(..., description="Start date of period")
    end_date: str = Field(..., description="End date of period")
    line_chart: Optional[str] = Field(None, description="Base64-encoded PNG line chart")
    data: list[SalesTrendDataPoint] = Field(default_factory=list, description="Daily data points")
    summary: SalesTrendSummary = Field(..., description="Period summary statistics")


@router.get(
    "/sales-trend",
    response_model=SalesTrendResponse,
    summary="Get Sales Trend Chart",
    description="""
    Returns a line chart showing Revenue vs COGS trend over a date range.
    
    **Chart Features:**
    - **Blue line**: Daily revenue
    - **Red dashed line**: Daily COGS (Cost of Goods Sold)
    - **Green shaded area**: Gross profit margin
    - **Legend**: Top-right corner
    - **Grid**: For readability
    
    **Business Date Logic (Law 4):**
    - Groups sales by Almaty business date
    - Business day starts at 06:00 AM Almaty time
    
    **Financial Precision (Law 2):**
    - All values use Decimal precision
    - Returned as strings to preserve precision
    
    **Validation:**
    - start_date must be <= end_date
    - Maximum range: 365 days
    """
)
async def get_sales_trend_chart(
    start_date: date = Query(
        ...,
        description="Start date (YYYY-MM-DD, inclusive)"
    ),
    end_date: date = Query(
        ...,
        description="End date (YYYY-MM-DD, inclusive)"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sales trend line chart with Revenue vs COGS visualization.
    
    Returns:
    - Line chart showing daily revenue (blue) and COGS (red)
    - Daily data points with revenue, cogs, profit, margin
    - Summary statistics (totals, averages)
    """
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be less than or equal to end_date"
        )
    
    # Limit to 365 days max
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        raise HTTPException(
            status_code=422,
            detail=f"Date range too large ({days_diff} days). Maximum is 365 days."
        )
    
    try:
        result = await ProductSalesChartService.get_sales_trend(
            db=db,
            start_date=start_date,
            end_date=end_date
        )
        
        return SalesTrendResponse(
            status="success",
            start_date=result["start_date"],
            end_date=result["end_date"],
            line_chart=result["line_chart"],
            data=[SalesTrendDataPoint(**item) for item in result["data"]],
            summary=SalesTrendSummary(**result["summary"])
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate trend chart: {str(e)}"
        )


@router.get(
    "/ingredient-usage",
    summary="Get Ingredient Usage Chart",
    description="Top 5 ingredients by usage cost over time (Multi-line chart)."
)
async def get_ingredient_usage_chart(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db)
):
    from datetime import timedelta
    
    if not end_date:
        end_date = get_business_date()
    if not start_date:
        start_date = end_date - timedelta(days=6)
        
    try:
        result = await ProductSalesChartService.get_ingredient_usage_chart(
            db=db,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        return {
            "status": "success",
            "data": result["data"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chart error: {str(e)}"
        )


@router.get("/dashboard", response_class=HTMLResponse, summary="Dashboard UI")
async def get_dashboard_ui():
    """
    Serve the dashboard HTML interface.
    """
    html_path = Path("app/templates/dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
