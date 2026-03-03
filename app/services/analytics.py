"""
WENDRINK ERP - Analytics Service

Reporting and analytics calculations.

Reports:
1. Product Profitability
2. Inventory Analytics
3. Dashboard Summary
4. Audit Trail

LAWS ENFORCED:
- Law 1: Ledger-First (all calculations via SUM)
- Law 2: Decimal Only
- Law 4: Almaty Business Date
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance_ledger import FinanceLedger
from app.models.ingredient import Ingredient
from app.models.inventory_ledger import InventoryLedger
from app.models.product import Product
from app.models.recipe import Recipe
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.utils.timezone import get_business_date


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProductProfit:
    """Product profitability data."""
    product_id: UUID
    product_name: str
    quantity_sold: int
    revenue: Decimal
    cogs: Decimal  # Calculated from ingredients (placeholder for now)
    profit: Decimal
    margin_percent: Decimal


@dataclass
class ProductProfitabilityReport:
    """Product profitability report for a date."""
    business_date: date
    products: list[ProductProfit]
    total_revenue: Decimal
    total_cogs: Decimal
    total_profit: Decimal
    avg_margin_percent: Decimal


@dataclass
class IngredientStock:
    """Current stock status for an ingredient."""
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    current_stock: Decimal
    current_wac: Decimal
    total_value: Decimal
    is_low_stock: bool
    is_negative: bool


@dataclass
class InventoryStatusReport:
    """Inventory status report."""
    as_of_date: date
    ingredients: list[IngredientStock]
    total_value: Decimal
    low_stock_count: int
    negative_stock_count: int


@dataclass
class DashboardSummary:
    """Dashboard summary for a business date."""
    business_date: date
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal
    waste_amount: Decimal
    opex: Decimal
    opex_breakdown: dict[str, Decimal]
    net_profit: Decimal
    net_margin_percent: Decimal
    is_profitable: bool
    transaction_count: int


@dataclass
class AuditEntry:
    """Single audit trail entry."""
    id: UUID
    event_type: str
    change_amount: Decimal
    unit_cost: Decimal | None
    weighted_average_cost: Decimal
    cost_snapshot: Decimal
    negative_stock: bool
    reason: str | None
    business_date: date
    created_at: str  # ISO format
    running_balance: Decimal  # Calculated


@dataclass
class AuditTrailReport:
    """Audit trail for an ingredient."""
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    start_date: date
    end_date: date
    entries: list[AuditEntry]
    starting_balance: Decimal
    ending_balance: Decimal


@dataclass
class ProductCostItem:
    """Theoretical cost for a product."""
    product_id: UUID
    product_name: str
    category: str | None
    sale_price: Decimal
    cost: Decimal
    gross_margin: Decimal
    gross_margin_percent: Decimal
    pos_code: int | None = None
    serving_unit: str | None = None
    serving_size: str | None = None


@dataclass
class ProductCostReport:
    """Product cost report."""
    business_date: date
    products: list[ProductCostItem]
    total_products: int
    avg_margin_percent: Decimal


@dataclass
class VarianceItem:
    """Theoretical vs actual variance item."""
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    theory_qty: Decimal
    fact_qty: Decimal
    diff_qty: Decimal
    diff_amount: Decimal
    variance_percent: Decimal
    is_overconsumption: bool


@dataclass
class VarianceReport:
    """Daily variance report."""
    business_date: date
    items: list[VarianceItem]


# =============================================================================
# Analytics Service
# =============================================================================

class AnalyticsService:
    """
    Service for reporting and analytics.
    
    All calculations use Decimal and ledger SUM.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # 1. Product Profitability
    # =========================================================================
    
    async def get_product_profitability(
        self,
        business_date: date,
    ) -> ProductProfitabilityReport:
        """
        Calculate profitability per product for a date.
        
        Revenue = SUM(sale_items.line_total) where sale.business_date = X
        Profit = Revenue - COGS (approximated from sale.total_cost proportionally)
        """
        # Get sales for the date with items
        sales_result = await self.session.execute(
            select(Sale)
            .where(Sale.business_date == business_date)
        )
        sales = sales_result.scalars().all()
        
        # Aggregate by product
        product_data: dict[UUID, dict] = {}
        
        for sale in sales:
            # Load items
            items_result = await self.session.execute(
                select(SaleItem).where(SaleItem.sale_id == sale.id)
            )
            items = items_result.scalars().all()
            
            # Calculate COGS using captured data or fallback to proportional
            sale_total = sale.total_amount
            sale_cogs = sale.total_cost
            
            for item in items:
                product_id = item.product_id
                if product_id not in product_data:
                    # Get product name
                    product = await self.session.get(Product, product_id)
                    unit_cogs = await self._get_theoretical_unit_cogs(product_id)
                    
                    product_data[product_id] = {
                        "product_name": product.name if product else "Unknown",
                        "quantity_sold": 0,
                        "revenue": Decimal("0"),
                        "cogs": Decimal("0"),
                        "unit_cogs": unit_cogs,
                    }
                
                product_data[product_id]["quantity_sold"] += item.quantity
                product_data[product_id]["revenue"] += item.line_total
                
                # Cogs is qty * unit_cogs (as requested: recipe.quantity * WAC)
                product_data[product_id]["cogs"] += product_data[product_id]["unit_cogs"] * item.quantity
        
        # Build product profit list
        products: list[ProductProfit] = []
        total_revenue = Decimal("0")
        total_cogs = Decimal("0")
        
        for product_id, data in product_data.items():
            revenue = data["revenue"]
            cogs = data["cogs"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            profit = revenue - cogs
            margin = self._calculate_margin(profit, revenue)
            
            products.append(ProductProfit(
                product_id=product_id,
                product_name=data["product_name"],
                quantity_sold=data["quantity_sold"],
                revenue=revenue,
                cogs=cogs,
                profit=profit,
                margin_percent=margin,
            ))
            
            total_revenue += revenue
            total_cogs += cogs
            
        # Sort by profit (descending)
        products.sort(key=lambda x: x.profit, reverse=True)
        
        total_profit = total_revenue - total_cogs
        avg_margin = self._calculate_margin(total_profit, total_revenue)
        
        return ProductProfitabilityReport(
            business_date=business_date,
            products=products,
            total_revenue=total_revenue,
            total_cogs=total_cogs,
            total_profit=total_profit,
            avg_margin_percent=avg_margin,
        )

    # =========================================================================
    # 5. Variance Report
    # =========================================================================

    async def get_variance_report(self, business_date: date) -> VarianceReport:
        """Calculate theoretical vs actual consumption for a given day."""
        ingredients = (await self.session.execute(select(Ingredient))).scalars().all()
        ing_dict = {i.id: i for i in ingredients}
        
        ledger_result = await self.session.execute(
            select(
                InventoryLedger.ingredient_id,
                func.sum(func.abs(InventoryLedger.change_amount)).label('fact_qty')
            )
            .where(
                InventoryLedger.business_date == business_date,
                InventoryLedger.event_type == 'SALE'
            )
            .group_by(InventoryLedger.ingredient_id)
        )
        fact_data = {row.ingredient_id: Decimal(str(row.fact_qty)) for row in ledger_result.fetchall()}
        
        sales = (await self.session.execute(
            select(Sale.id).where(Sale.business_date == business_date)
        )).scalars().all()
        
        theory_data = {}
        if sales:
            sale_items_query = select(SaleItem).where(SaleItem.sale_id.in_(sales))
            sale_items = (await self.session.execute(sale_items_query)).scalars().all()
            
            for item in sale_items:
                r_items = (await self.session.execute(
                    select(Recipe).where(Recipe.product_id == item.product_id)
                )).scalars().all()
                
                for r_item in r_items:
                    qty = Decimal(str(r_item.quantity)) * Decimal(str(item.quantity))
                    theory_data[r_item.ingredient_id] = theory_data.get(r_item.ingredient_id, Decimal("0")) + qty
                        
        items = []
        all_ids = set(fact_data.keys()) | set(theory_data.keys())
        for ing_id in all_ids:
            ing = ing_dict.get(ing_id)
            if not ing: continue
            
            theory = theory_data.get(ing_id, Decimal("0"))
            fact = fact_data.get(ing_id, Decimal("0"))
            
            diff_qty = fact - theory
            wac = await self._get_latest_wac_for_date(ing_id, business_date)
            diff_amount = diff_qty * wac
            
            if theory > 0:
                var_pct = (diff_qty / theory) * Decimal("100")
            else:
                var_pct = Decimal("100") if fact > 0 else Decimal("0")
                
            items.append(VarianceItem(
                ingredient_id=ing_id,
                ingredient_name=ing.name,
                unit=ing.unit,
                theory_qty=theory.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                fact_qty=fact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                diff_qty=diff_qty.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                diff_amount=diff_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                variance_percent=var_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                is_overconsumption=var_pct > Decimal("5"),
            ))
            
        return VarianceReport(
            business_date=business_date, 
            items=sorted(items, key=lambda x: x.diff_qty, reverse=True)
        )

    async def _get_latest_wac_for_date(self, ingredient_id: UUID, date_limit: date) -> Decimal:
        wac_query = (
            select(InventoryLedger.weighted_average_cost)
            .where(
                InventoryLedger.ingredient_id == ingredient_id, 
                InventoryLedger.business_date <= date_limit
            )
            .order_by(InventoryLedger.created_at.desc())
            .limit(1)
        )
        return Decimal(str((await self.session.execute(wac_query)).scalar() or "0"))
    
    async def _get_theoretical_unit_cogs(self, product_id: UUID) -> Decimal:
        """Calculate theoretical unit COGS using active recipe and current WAC."""
        items = (await self.session.execute(
            select(Recipe).where(Recipe.product_id == product_id)
        )).scalars().all()
        
        unit_cogs = Decimal("0")
        for item in items:
            wac_query = (
                select(InventoryLedger.weighted_average_cost)
                .where(InventoryLedger.ingredient_id == item.ingredient_id)
                .order_by(InventoryLedger.created_at.desc())
                .limit(1)
            )
            wac = (await self.session.execute(wac_query)).scalar() or Decimal("0")
            unit_cogs += item.quantity * wac
            
        return unit_cogs

    
    # =========================================================================
    # 2. Inventory Analytics
    # =========================================================================
    
    async def get_inventory_status(
        self,
        low_stock_threshold: Decimal = Decimal("20"),
    ) -> InventoryStatusReport:
        """
        Get current inventory status for all ingredients.
        
        Current stock = SUM(inventory_ledger.change_amount).
        Low stock = current_stock < threshold.
        
        OPTIMIZED: Single query with GROUP BY instead of N+1 pattern.
        CACHED: 5-minute TTL for dashboard performance.
        """
        from app.utils.cache import get_cached, set_cached
        
        cache_key = f"inventory_status:{low_stock_threshold}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Single query: balance + WAC for ALL ingredients at once
        # This replaces 110 individual queries (2 per ingredient × 55)
        from sqlalchemy import text
        
        result = await self.session.execute(
            text("""
                SELECT 
                    i.id,
                    i.name,
                    i.unit,
                    COALESCE(SUM(il.change_amount), 0) as current_stock,
                    COALESCE(
                        (SELECT il2.weighted_average_cost 
                         FROM inventory_ledger il2 
                         WHERE il2.ingredient_id = i.id 
                         ORDER BY il2.created_at DESC LIMIT 1),
                        0
                    ) as current_wac
                FROM ingredients i
                LEFT JOIN inventory_ledger il ON il.ingredient_id = i.id
                GROUP BY i.id, i.name, i.unit
                ORDER BY i.name
            """)
        )
        rows = result.fetchall()
        
        ingredient_stocks: list[IngredientStock] = []
        total_value = Decimal("0")
        low_stock_count = 0
        negative_stock_count = 0
        
        for row in rows:
            ing_id, name, unit, stock_raw, wac_raw = row
            current_stock = Decimal(str(stock_raw))
            current_wac = Decimal(str(wac_raw))
            
            # Calculate value
            value = current_stock * current_wac if current_stock > 0 else Decimal("0")
            
            # Check stock status
            is_negative = current_stock < 0
            is_low = current_stock < low_stock_threshold and not is_negative
            
            if is_negative:
                negative_stock_count += 1
            elif is_low:
                low_stock_count += 1
            
            ingredient_stocks.append(IngredientStock(
                ingredient_id=ing_id,
                ingredient_name=name,
                unit=unit,
                current_stock=current_stock,
                current_wac=current_wac,
                total_value=value,
                is_low_stock=is_low,
                is_negative=is_negative,
            ))
            
            total_value += value
        
        # Sort: negative first, then low stock, then by name
        ingredient_stocks.sort(key=lambda x: (
            not x.is_negative,  # Negative first
            not x.is_low_stock,  # Then low stock
            x.ingredient_name,  # Then alphabetically
        ))
        
        report = InventoryStatusReport(
            as_of_date=get_business_date(),
            ingredients=ingredient_stocks,
            total_value=total_value,
            low_stock_count=low_stock_count,
            negative_stock_count=negative_stock_count,
        )
        
        # Cache for 5 minutes
        set_cached(cache_key, report, ttl=300)
        
        return report
    
    # =========================================================================
    # 3. Dashboard Summary
    # =========================================================================
    
    async def get_dashboard_summary(
        self,
        business_date: date | None = None,
    ) -> DashboardSummary:
        """
        Get dashboard summary for a business date.
        
        Uses today's business date if not specified.
        CACHED: 5-minute TTL for dashboard performance.
        """
        from app.services.finance import FinanceService
        from app.utils.cache import get_cached, set_cached

        if business_date is None:
            business_date = get_business_date()
        
        cache_key = f"dashboard:{business_date}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Revenue
        revenue_result = await self.session.execute(
            select(func.sum(Sale.total_amount))
            .where(Sale.business_date == business_date)
        )
        revenue = revenue_result.scalar() or Decimal("0")
        
        # Transaction count
        count_result = await self.session.execute(
            select(func.count(Sale.id))
            .where(Sale.business_date == business_date)
        )
        transaction_count = count_result.scalar() or 0
        
        # COGS
        cogs_result = await self.session.execute(
            select(func.sum(Sale.total_cost))
            .where(Sale.business_date == business_date)
        )
        cogs = cogs_result.scalar() or Decimal("0")
        
        # WASTE
        waste_result = await self.session.execute(
            select(func.sum(InventoryLedger.cost_snapshot))
            .where(InventoryLedger.event_type == InventoryEventType.WASTE.value)
            .where(InventoryLedger.business_date == business_date)
        )
        waste = waste_result.scalar() or Decimal("0")
        
        # OPEX using FinanceService
        finance_service = FinanceService(self.session)
        daily_opex = await finance_service.get_daily_opex(business_date)
        opex = daily_opex.total
        opex_breakdown = daily_opex.breakdown
        
        # Calculate profits and margins
        gross_profit = revenue - cogs
        net_profit = gross_profit - waste - opex
        gross_margin = self._calculate_margin(gross_profit, revenue)
        net_margin = self._calculate_margin(net_profit, revenue)
        
        summary = DashboardSummary(
            business_date=business_date,
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_percent=gross_margin,
            waste_amount=waste,
            opex=opex,
            opex_breakdown=opex_breakdown,
            net_profit=net_profit,
            net_margin_percent=net_margin,
            is_profitable=net_profit > Decimal("0"),
            transaction_count=transaction_count,
        )
        
        # Cache for 5 minutes
        set_cached(cache_key, summary, ttl=300)
        
        return summary
    
    # =========================================================================
    # 4. Audit Trail
    # =========================================================================
    
    async def get_audit_trail(
        self,
        ingredient_id: UUID,
        start_date: date,
        end_date: date,
    ) -> AuditTrailReport:
        """
        Get complete audit trail for an ingredient.
        
        Shows all movements with running balance.
        """
        # Get ingredient
        ingredient = await self.session.get(Ingredient, ingredient_id)
        if ingredient is None:
            raise ValueError(f"Ingredient {ingredient_id} not found")
        
        # Get starting balance (sum of all events before start_date)
        starting_result = await self.session.execute(
            select(func.sum(InventoryLedger.change_amount))
            .where(InventoryLedger.ingredient_id == ingredient_id)
            .where(InventoryLedger.business_date < start_date)
        )
        starting_balance = starting_result.scalar() or Decimal("0")
        
        # Get all events in the date range
        events_result = await self.session.execute(
            select(InventoryLedger)
            .where(InventoryLedger.ingredient_id == ingredient_id)
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
            .order_by(InventoryLedger.business_date, InventoryLedger.created_at)
        )
        events = events_result.scalars().all()
        
        # Build audit entries with running balance
        entries: list[AuditEntry] = []
        running_balance = starting_balance
        
        for event in events:
            running_balance += event.change_amount
            
            entries.append(AuditEntry(
                id=event.id,
                event_type=event.event_type,
                change_amount=event.change_amount,
                unit_cost=event.unit_cost,
                weighted_average_cost=event.weighted_average_cost,
                cost_snapshot=event.cost_snapshot,
                negative_stock=event.negative_stock,
                reason=event.reason,
                business_date=event.business_date,
                created_at=event.created_at.isoformat() if event.created_at else "",
                running_balance=running_balance,
            ))
        
        return AuditTrailReport(
            ingredient_id=ingredient_id,
            ingredient_name=ingredient.name,
            unit=ingredient.unit,
            start_date=start_date,
            end_date=end_date,
            entries=entries,
            starting_balance=starting_balance,
            ending_balance=running_balance,
        )

    # =========================================================================
    # 5. Product Costs (Theoretical)
    # =========================================================================

    async def get_product_costs(self) -> ProductCostReport:
        """
        Calculate theoretical cost (COGS) for all active products.

        Priority for unit cost:
          1. ingredient.current_price  (set manually in "Цены сырья")
          2. latest WAC from inventory_ledger  (auto-updated on SUPPLY)
          3. ingredient.initial_cost  (initial seed value)

        Uses a single SQL query — no ORM lazy loading issues.
        """
        from sqlalchemy import text

        # Single SQL: products + recipes + ingredients + latest WAC
        rows = await self.session.execute(text("""
            SELECT
                p.id           AS product_id,
                p.name         AS product_name,
                p.category     AS category,
                p.pos_code     AS pos_code,
                p.price        AS sale_price,
                p.serving_unit AS serving_unit,
                p.serving_size AS serving_size,
                r.quantity     AS recipe_qty,
                i.current_price AS current_price,
                i.initial_cost  AS initial_cost,
                (
                    SELECT il.weighted_average_cost
                    FROM inventory_ledger il
                    WHERE il.ingredient_id = i.id
                    ORDER BY il.created_at DESC
                    LIMIT 1
                ) AS wac
            FROM products p
            JOIN recipes r   ON r.product_id    = p.id
            JOIN ingredients i ON i.id          = r.ingredient_id
            WHERE p.is_active = 1
            ORDER BY p.pos_code, i.name
        """))
        recipe_rows = rows.fetchall()

        # Aggregate: product_id → cost accumulator
        from collections import defaultdict
        product_info: dict = {}   # product_id → meta
        product_cost: dict = defaultdict(lambda: Decimal("0"))

        for row in recipe_rows:
            # SQLite may return UUID as bytes — normalize to str
            pid = str(row.product_id) if row.product_id else None
            if not pid:
                continue

            # Save product meta once
            if pid not in product_info:
                product_info[pid] = {
                    "product_name": row.product_name,
                    "category":     row.category,
                    "pos_code":     row.pos_code,
                    "sale_price":   Decimal(str(row.sale_price)),
                    "serving_unit": row.serving_unit,
                    "serving_size": row.serving_size,
                }

            # Determine unit cost: current_price > WAC > initial_cost
            if row.current_price is not None:
                unit_cost = Decimal(str(row.current_price))
            elif row.wac is not None:
                unit_cost = Decimal(str(row.wac))
            elif row.initial_cost is not None:
                unit_cost = Decimal(str(row.initial_cost))
            else:
                unit_cost = Decimal("0")

            # Line cost rounded to 2 dp (matches Excel рehaviour: round each ingredient line)
            line_cost = (Decimal(str(row.recipe_qty)) * unit_cost).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            product_cost[pid] += line_cost

        # Build result items
        items = []
        for pid, meta in product_info.items():
            cost = product_cost[pid].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            sale_price = meta["sale_price"]
            margin = sale_price - cost
            margin_percent = self._calculate_margin(margin, sale_price)

            items.append(ProductCostItem(
                product_id=pid,
                product_name=meta["product_name"],
                category=meta["category"],
                pos_code=meta["pos_code"],
                sale_price=sale_price,
                cost=cost,
                gross_margin=margin,
                gross_margin_percent=margin_percent,
                serving_unit=meta["serving_unit"],
                serving_size=meta["serving_size"],
            ))


        # Sort by pos_code ASC (по порядку кода)
        items.sort(key=lambda x: int(x.pos_code) if x.pos_code and str(x.pos_code).isdigit() else 9999)
        
        avg_margin = (
            sum(i.gross_margin_percent for i in items) / len(items)
            if items else Decimal("0")
        )
        
        return ProductCostReport(
            business_date=get_business_date(),
            products=items,
            total_products=len(items),
            avg_margin_percent=avg_margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _calculate_margin(self, profit: Decimal, revenue: Decimal) -> Decimal:
        """Calculate profit margin percentage."""
        if revenue == Decimal("0"):
            return Decimal("0.00")
        return (profit / revenue * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
