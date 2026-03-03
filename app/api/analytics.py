"""
WENDRINK ERP - Analytics Charts API

Advanced analytics endpoints for inventory forecasting and category analysis.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.forecast import InventoryForecastService
from app.utils.timezone import get_business_date


router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class ForecastItem(BaseModel):
    """Single ingredient forecast."""
    ingredient: str
    ingredient_id: str
    unit: str
    current_stock: str
    daily_usage_avg: str
    trend_percent: float
    predicted_daily: str
    days_left: Optional[float]
    stockout_date: Optional[str]
    order_by_date: Optional[str]
    order_amount: str
    status: str


class ForecastSummary(BaseModel):
    """Forecast summary."""
    total_ingredients: int
    urgent_count: int
    warning_count: int
    ok_count: int


class InventoryForecastResponse(BaseModel):
    """Inventory forecast response."""
    status: str = "success"
    analysis_date: str
    analysis_days: int
    forecast_days: int
    line_chart: Optional[str] = Field(None, description="Base64 PNG chart")
    forecasts: list[ForecastItem]
    priority_list: dict
    summary: ForecastSummary


class InventoryStatusItem(BaseModel):
    """Inventory status item."""
    ingredient_id: str
    ingredient: str
    unit: str
    current_stock: float
    status: str


class InventoryStatusResponse(BaseModel):
    """Inventory status response."""
    status: str = "success"
    bar_chart: Optional[str] = Field(None, description="Base64 PNG chart")
    data: dict
    summary: dict


class CategorySalesItem(BaseModel):
    """Category sales item."""
    category: str
    revenue: str
    percentage: float
    products_count: int


class CategorySalesResponse(BaseModel):
    """Category sales response."""
    status: str = "success"
    business_date: str
    bar_chart: Optional[str] = Field(None, description="Base64 PNG bar chart")
    pie_chart: Optional[str] = Field(None, description="Base64 PNG pie chart")
    data: list[CategorySalesItem]
    total_revenue: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/inventory-forecast",
    response_model=InventoryForecastResponse,
    summary="Get Inventory Forecast",
    description="""
    🔮 **ПРОГНОЗ ОСТАТКОВ ИНГРЕДИЕНТОВ**
    
    Анализирует продажи за последние N дней и прогнозирует:
    - Когда закончится каждый ингредиент
    - Какой тренд расхода (растёт/падает)
    - Когда нужно заказать
    - Сколько заказать
    
    **Алгоритм:**
    1. Берём продажи за последние N дней
    2. Считаем расход ингредиентов по рецептам
    3. Определяем тренд (линейная регрессия)
    4. Прогнозируем будущий расход
    5. Делим остаток на прогноз = дней до конца
    
    **Цвета статусов:**
    - 🔴 critical: < 7 дней
    - 🟡 warning: 7-14 дней  
    - 🟢 ok: > 14 дней
    """,
)
async def get_inventory_forecast(
    analysis_days: int = Query(7, ge=3, le=30, description="Дней для анализа"),
    forecast_days: int = Query(30, ge=7, le=90, description="Дней для прогноза"),
    db: AsyncSession = Depends(get_db),
) -> InventoryForecastResponse:
    """Get inventory forecast for all ingredients."""
    
    service = InventoryForecastService(db)
    
    try:
        result = await service.get_inventory_forecast(
            analysis_days=analysis_days,
            forecast_days=forecast_days,
        )
        
        return InventoryForecastResponse(
            status=result["status"],
            analysis_date=result["analysis_date"],
            analysis_days=result["analysis_days"],
            forecast_days=result["forecast_days"],
            line_chart=result["line_chart"],
            forecasts=[ForecastItem(**f) for f in result["forecasts"]],
            priority_list=result["priority_list"],
            summary=ForecastSummary(**result["summary"]),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast error: {str(e)}"
        )


@router.get(
    "/inventory-status",
    response_model=InventoryStatusResponse,
    summary="Get Inventory Status",
    description="""
    📦 **СТАТУС СКЛАДА**
    
    Показывает текущее состояние всех ингредиентов:
    - 🔴 critical: критически низкий уровень
    - 🟡 warning: требует внимания
    - 🟢 ok: достаточный запас
    
    Включает горизонтальную диаграмму с цветами.
    """,
)
async def get_inventory_status(
    db: AsyncSession = Depends(get_db),
) -> InventoryStatusResponse:
    """Get current inventory status."""
    
    service = InventoryForecastService(db)
    
    try:
        result = await service.get_inventory_status()
        
        return InventoryStatusResponse(
            status=result["status"],
            bar_chart=result["bar_chart"],
            data=result["data"],
            summary=result["summary"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Status error: {str(e)}"
        )


@router.get(
    "/category-sales",
    response_model=CategorySalesResponse,
    summary="Get Category Sales",
    description="""
    📊 **ПРОДАЖИ ПО КАТЕГОРИЯМ**
    
    Группирует продажи по категориям продуктов:
    - Мороженое
    - Молочные чаи
    - Фруктовые чаи
    - Кофе
    - Вафли
    - Допы
    
    Включает bar chart и pie chart.
    """,
)
async def get_category_sales(
    business_date: Optional[date] = Query(None, description="Дата (по умолчанию сегодня)"),
    db: AsyncSession = Depends(get_db),
) -> CategorySalesResponse:
    """Get sales breakdown by category."""
    
    if business_date is None:
        business_date = get_business_date()
    
    service = InventoryForecastService(db)
    
    try:
        result = await service.get_category_sales(business_date)
        
        return CategorySalesResponse(
            status=result["status"],
            business_date=result["business_date"],
            bar_chart=result["bar_chart"],
            pie_chart=result["pie_chart"],
            data=[CategorySalesItem(**d) for d in result["data"]],
            total_revenue=result["total_revenue"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Category sales error: {str(e)}"
        )


class InsightResponse(BaseModel):
    id: str
    type: str  # "critical", "warning", "success"
    message: str


@router.get(
    "/insights",
    response_model=list[InsightResponse],
    summary="Daily AI Insights",
)
async def get_daily_insights(db: AsyncSession = Depends(get_db)):
    """Smart engine for daily owner alerts"""
    from decimal import Decimal
    from app.models.ingredient import Ingredient
    from app.models.inventory_ledger import InventoryLedger
    from app.models.product import Product
    from app.models.recipe import Recipe
    from app.models.finance_ledger import FinanceLedger
    from app.services.analytics import AnalyticsService
    from app.utils.timezone import get_business_date, get_utc_now, utc_to_almaty
    from sqlalchemy import select, func, and_
    from sqlalchemy.orm import selectinload

    insights = []
    business_date = get_business_date()
    current_time = utc_to_almaty(get_utc_now())

    # ─── 1. P&L сегодня ───────────────────────────────────────────────
    analytics_service = AnalyticsService(db)
    summary = await analytics_service.get_dashboard_summary(business_date)

    if summary.revenue > 0:
        if summary.net_profit < 0:
            loss = abs(int(summary.net_profit))
            insights.append(InsightResponse(
                id="pnl_loss", type="critical",
                message=f"Смена убыточна: −{loss:,} ₸. Расходы перекрывают выручку.".replace(",", " ")
            ))
        elif summary.gross_margin_percent >= Decimal("65") and summary.net_profit > 0:
            insights.append(InsightResponse(
                id="pnl_good", type="success",
                message=f"Маржа {summary.gross_margin_percent:.0f}% — отлично! Чистая прибыль: {int(summary.net_profit):,} ₸.".replace(",", " ")
            ))
        elif summary.gross_margin_percent < Decimal("40"):
            insights.append(InsightResponse(
                id="pnl_low_margin", type="warning",
                message=f"Низкая маржа {summary.gross_margin_percent:.0f}%. Проверьте себестоимость рецептов."
            ))

    # ─── 2. МАРЖА ПО ПРОДУКТАМ: Рецепт × текущий WAC vs Цена продажи ──
    # Рецепты фиксированы компанией и не меняются.
    # WAC растёт со временем (сырьё дорожает) → маржа падает → нужно поднимать цены.
    # Проверяем: если рецепт × актуальный WAC даёт маржу < 20% → сигнал поднять цену.

    latest_wac_sq = (
        select(
            InventoryLedger.ingredient_id,
            func.max(InventoryLedger.created_at).label("max_ts")
        )
        .where(InventoryLedger.weighted_average_cost > 0)
        .group_by(InventoryLedger.ingredient_id)
        .subquery()
    )
    wac_rows = await db.execute(
        select(InventoryLedger.ingredient_id, InventoryLedger.weighted_average_cost)
        .join(latest_wac_sq, and_(
            InventoryLedger.ingredient_id == latest_wac_sq.c.ingredient_id,
            InventoryLedger.created_at == latest_wac_sq.c.max_ts
        ))
        .where(InventoryLedger.weighted_average_cost > 0)
    )
    wac_map = {str(r.ingredient_id): float(r.weighted_average_cost) for r in wac_rows}

    # Загружаем initial_cost отдельным запросом — избегаем lazy loading в async
    ing_cost_rows = await db.execute(
        select(Ingredient.id, Ingredient.initial_cost)
    )
    ing_cost_map = {str(r.id): float(r.initial_cost or 0) for r in ing_cost_rows}

    # Загружаем рецепты отдельно (без цепочки selectinload, т.к. Product.recipes уже lazy="selectin")
    products_res = await db.execute(select(Product))
    products = products_res.scalars().all()

    recipes_res = await db.execute(select(Recipe))
    all_recipes = recipes_res.scalars().all()
    # Группируем рецепты по product_id
    recipes_by_product: dict = {}
    for r in all_recipes:
        pid = str(r.product_id)
        recipes_by_product.setdefault(pid, []).append(r)

    low_margin_products = []  # маржа < 20% по рецепту × текущий WAC

    for prod in products:
        prod_recipes = recipes_by_product.get(str(prod.id), [])
        if not prod_recipes:
            continue
        # Себестоимость = рецепт (фиксированный) × текущий WAC (меняется)
        recipe_cost = sum(
            float(r.quantity) * wac_map.get(str(r.ingredient_id), ing_cost_map.get(str(r.ingredient_id), 0))
            for r in prod_recipes
        )
        price = float(prod.price)
        if price > 0 and recipe_cost > 0:
            margin = (price - recipe_cost) / price * 100
            if margin < 20:
                low_margin_products.append(
                    f"{prod.name} (маржа {margin:.0f}%, себес {recipe_cost:.0f} ₸, цена {price:.0f} ₸)"
                )

    if low_margin_products:
        names = "; ".join(low_margin_products[:2])
        suffix = f" и ещё {len(low_margin_products) - 2}" if len(low_margin_products) > 2 else ""
        insights.append(InsightResponse(
            id="low_margin_products", type="critical",
            message=f"Сырьё подорожало! Низкая маржа: {names}{suffix}. Пора поднимать цены."
        ))

    # ─── 2b. ВЕРИФИКАЦИЯ РАСЧЁТОВ: Рецепт × WAC_продажи vs SaleItem.total_cost ──
    # Логика: когда Z-отчёт проводится, система пишет SaleItem.total_cost = рецепт × WAC.
    # Мы независимо пересчитываем то же самое и сравниваем.
    # Совпадает → всё считает правильно. Расходится → баг в данных.
    # Используем WAC из сегодняшних SALE-событий ledger (именно тот WAC что был при продаже).
    if summary.revenue > 0:
        from app.models.sale import Sale
        from app.models.sale_item import SaleItem

        # WAC по ингредиентам из сегодняшних SALE-событий
        sale_wac_res = await db.execute(
            select(
                InventoryLedger.ingredient_id,
                func.avg(InventoryLedger.weighted_average_cost).label("avg_wac")
            )
            .where(and_(
                InventoryLedger.business_date == business_date,
                InventoryLedger.event_type == "SALE",
                InventoryLedger.weighted_average_cost > 0
            ))
            .group_by(InventoryLedger.ingredient_id)
        )
        sale_wac_map = {str(r.ingredient_id): float(r.avg_wac) for r in sale_wac_res}

        # Фактически записанный cost из SaleItem за сегодня
        sale_items_res = await db.execute(
            select(
                SaleItem.product_id,
                func.sum(SaleItem.quantity).label("total_qty"),
                func.sum(SaleItem.total_cost).label("total_cost"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(and_(
                Sale.business_date == business_date,
                SaleItem.total_cost.isnot(None)
            ))
            .group_by(SaleItem.product_id)
        )
        sale_item_map = {
            str(r.product_id): {
                "qty": int(r.total_qty or 0),
                "cost": float(r.total_cost or 0)
            }
            for r in sale_items_res
        }

        verified_count = 0
        mismatch_products = []

        for prod in products:
            prod_recipes = recipes_by_product.get(str(prod.id), [])
            if not prod_recipes:
                continue
            pid = str(prod.id)
            if pid not in sale_item_map or sale_item_map[pid]["qty"] == 0:
                continue  # продукт не продавался сегодня

            # Независимый пересчёт: рецепт × WAC_продажи
            recipe_cost_at_sale = sum(
                float(r.quantity) * sale_wac_map.get(
                    str(r.ingredient_id),
                    wac_map.get(str(r.ingredient_id), ing_cost_map.get(str(r.ingredient_id), 0))
                )
                for r in prod_recipes
            )

            if recipe_cost_at_sale <= 0:
                continue

            actual_cost_per_unit = sale_item_map[pid]["cost"] / sale_item_map[pid]["qty"]
            variance = abs(actual_cost_per_unit - recipe_cost_at_sale) / recipe_cost_at_sale * 100

            if variance <= 5:
                verified_count += 1  # всё совпало ✅
            else:
                mismatch_products.append(
                    f"{prod.name} (расч. {recipe_cost_at_sale:.0f} ₸, записано {actual_cost_per_unit:.0f} ₸, Δ{variance:.0f}%)"
                )

        if mismatch_products:
            names = "; ".join(mismatch_products[:2])
            suffix = f" и ещё {len(mismatch_products) - 2}" if len(mismatch_products) > 2 else ""
            insights.append(InsightResponse(
                id="cost_mismatch", type="warning",
                message=f"⚠️ Расхождение себестоимости (рецепт ≠ запись): {names}{suffix}. Проверьте данные."
            ))
        elif verified_count > 0:
            insights.append(InsightResponse(
                id="cost_verified", type="success",
                message=f"✅ Себестоимость проверена: расчёт совпадает по всем {verified_count} позициям."
            ))

    # ─── 3. Остатки склада — умный порог через norm_stock ─────────────
    stock_query = await db.execute(
        select(
            Ingredient.name,
            Ingredient.unit,
            Ingredient.norm_stock,
            func.sum(InventoryLedger.change_amount).label("current_stock")
        )
        .join(InventoryLedger, InventoryLedger.ingredient_id == Ingredient.id)
        .group_by(Ingredient.id, Ingredient.name, Ingredient.unit, Ingredient.norm_stock)
        .having(func.sum(InventoryLedger.change_amount) >= 0)
    )
    stock_rows = stock_query.all()

    critical_stock = []
    warning_stock = []

    for row in stock_rows:
        current = float(row.current_stock or 0)
        norm = float(row.norm_stock or 0)

        if norm > 0:
            ratio = current / norm
            if ratio < 0.25:
                critical_stock.append(row.name)
            elif ratio < 0.50:
                warning_stock.append(row.name)
        else:
            unit_lower = (row.unit or "").lower()
            if unit_lower in ("pcs", "pc", "шт", "шт.", "штук"):
                if current < 10:
                    critical_stock.append(row.name)
                elif current < 30:
                    warning_stock.append(row.name)
            elif unit_lower in ("кг", "kg", "л", "l", "liter"):
                if current < 0.5:
                    critical_stock.append(row.name)
                elif current < 2:
                    warning_stock.append(row.name)
            else:
                if current < 200:
                    critical_stock.append(row.name)
                elif current < 800:
                    warning_stock.append(row.name)

    if critical_stock:
        names = ", ".join(critical_stock[:3])
        suffix = f" и ещё {len(critical_stock) - 3}" if len(critical_stock) > 3 else ""
        insights.append(InsightResponse(
            id="stock_critical", type="critical",
            message=f"🚨 Критически мало: {names}{suffix}. Срочно пополните."
        ))
    elif warning_stock:
        names = ", ".join(warning_stock[:3])
        suffix = f" и ещё {len(warning_stock) - 3}" if len(warning_stock) > 3 else ""
        insights.append(InsightResponse(
            id="stock_warning", type="warning",
            message=f"⚠️ Заканчивается: {names}{suffix}. Запланируйте закупку."
        ))

    # ─── 4. Нет данных / напоминание о Z-отчёте ───────────────────────
    # Закрытие в ~23:00 → напоминание только с 22:00
    if summary.transaction_count == 0 and current_time.hour >= 22:
        insights.append(InsightResponse(
            id="no_zreport", type="warning",
            message="Нет данных за сегодня. Скоро закрытие — не забудьте загрузить Z-отчёт."
        ))

    # ─── 5. Зарплата не введена ────────────────────────────────────────
    # Данные вводятся в 23:00 → напоминание только с 22:00
    payroll_check = await db.execute(
        select(func.count(FinanceLedger.id))
        .where(and_(
            FinanceLedger.business_date == business_date,
            FinanceLedger.category == "SALARY"
        ))
    )
    payroll_count = payroll_check.scalar() or 0
    if payroll_count == 0 and summary.revenue > 0 and current_time.hour >= 22:
        insights.append(InsightResponse(
            id="no_payroll", type="warning",
            message="Зарплата за сегодня не введена. Не забудьте внести после закрытия."
        ))

    # ─── Всё хорошо ───────────────────────────────────────────────────
    if not insights and summary.revenue > 0:
        insights.append(InsightResponse(
            id="all_good", type="success",
            message=f"Всё в порядке. Выручка {int(summary.revenue):,} ₸, склад в норме.".replace(",", " ")
        ))

    return insights
