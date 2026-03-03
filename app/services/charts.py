"""
WENDRINK ERP - Product Sales Charts Service

Analytics and visualizations for product sales data.
Follows Law 2 (Decimal-only) and Law 4 (Almaty Business Date).
"""
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional
import base64
import io

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale import Sale, SaleItem
from app.models.product import Product


class ProductSalesChartService:
    """
    Generate charts for product sales analytics.
    
    Returns base64-encoded PNG images for:
    - Bar chart: Top products by quantity sold
    - Pie chart: Revenue distribution (top 10)
    """
    
    @staticmethod
    async def get_top_products(
        db: AsyncSession,
        business_date: date,
        limit: int = 15
    ) -> Dict[str, Any]:
        """
        Get top products with bar and pie charts.
        
        Args:
            db: Async database session
            business_date: Business date for filtering (Almaty timezone)
            limit: Maximum number of products to return (default 15)
            
        Returns:
            Dict containing:
            - bar_chart: Base64 PNG of bar chart (quantity)
            - pie_chart: Base64 PNG of pie chart (revenue %)
            - data: List of product data with quantity, revenue, percentage
            - total: Total revenue as string
        """
        # Query top products by quantity, joined with sales for business_date
        query = (
            select(
                Product.name,
                func.sum(SaleItem.quantity).label('qty'),
                func.sum(SaleItem.line_total).label('rev')
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.business_date == business_date)
            .group_by(Product.name)
            .order_by(func.sum(SaleItem.quantity).desc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        # Handle empty results
        if not rows:
            return {
                "business_date": str(business_date),
                "bar_chart": None,
                "pie_chart": None,
                "data": [],
                "total": "0.00"
            }
        
        # Extract data - using Decimal for financial calculations (Law 2)
        names = [r.name for r in rows]
        qtys = [int(r.qty) for r in rows]
        # Convert to Decimal for precise financial math
        revs_decimal = [Decimal(str(r.rev)) for r in rows]
        total_decimal = sum(revs_decimal, Decimal("0"))
        
        # Build response data
        data = []
        for r in rows:
            rev = Decimal(str(r.rev))
            percentage = (
                (rev / total_decimal * Decimal("100")).quantize(Decimal("0.1"))
                if total_decimal > Decimal("0") else Decimal("0")
            )
            data.append({
                "product": r.name,
                "quantity": int(r.qty),
                "revenue": str(rev.quantize(Decimal("0.01"))),
                "percentage": str(percentage)
            })
        
        # Generate charts (use float for matplotlib)
        revs_float = [float(r) for r in revs_decimal]
        bar_chart = ProductSalesChartService._create_bar_chart(names, qtys)
        pie_chart = ProductSalesChartService._create_pie_chart(names[:10], revs_float[:10])
        
        return {
            "business_date": str(business_date),
            "bar_chart": bar_chart,
            "pie_chart": pie_chart,
            "data": data,
            "total": str(total_decimal.quantize(Decimal("0.01")))
        }
    
    @staticmethod
    def _create_bar_chart(labels: List[str], values: List[int]) -> str:
        """
        Create a bar chart for product quantities.
        
        Returns base64-encoded PNG string.
        """
        plt.figure(figsize=(12, 7))
        
        # Modern color palette
        colors = ['#4A90E2'] * len(labels)
        
        bars = plt.bar(labels, values, color=colors, edgecolor='white', linewidth=0.5)
        
        # Add value labels on bars
        for bar, val in zip(bars, values):
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.01,
                str(val),
                ha='center',
                va='bottom',
                fontsize=9,
                fontweight='bold'
            )
        
        plt.xlabel('Продукты', fontsize=11, fontweight='bold')
        plt.ylabel('Количество проданных единиц', fontsize=11, fontweight='bold')
        plt.title('Топ-15 продуктов по количеству продаж', fontsize=14, fontweight='bold', pad=15)
        plt.xticks(rotation=45, ha='right', fontsize=9)
        plt.yticks(fontsize=9)
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Style improvements
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return img_base64
    
    @staticmethod
    def _create_pie_chart(labels: List[str], values: List[float]) -> str:
        """
        Create a pie chart for revenue distribution.
        
        Returns base64-encoded PNG string.
        """
        plt.figure(figsize=(10, 10))
        
        # Modern color palette
        colors = [
            '#4A90E2', '#50C878', '#FF6B6B', '#FFA500', '#9B59B6',
            '#1ABC9C', '#E74C3C', '#3498DB', '#F39C12', '#2ECC71'
        ]
        
        # Create pie with explode effect for top 3
        explode = [0.05 if i < 3 else 0 for i in range(len(values))]
        
        wedges, texts, autotexts = plt.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors[:len(values)],
            explode=explode,
            startangle=90,
            pctdistance=0.75,
            shadow=False
        )
        
        # Style the percentage labels
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        for text in texts:
            text.set_fontsize(9)
        
        plt.title('Топ-10 продуктов по выручке', fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return img_base64

    @staticmethod
    async def get_sales_trend(
        db: AsyncSession,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get sales trend with line chart showing Revenue vs COGS over time.
        
        Args:
            db: Async database session
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            Dict containing:
            - line_chart: Base64 PNG of line chart (Revenue blue, COGS red)
            - data: List of daily data points with revenue, cogs, profit, margin
            - summary: Aggregated totals and averages
            
        Law 2: All financial calculations use Decimal
        Law 4: Groups by business_date (Almaty timezone)
        """
        # 1. Query Sales (Revenue & COGS)
        sales_query = (
            select(
                Sale.business_date,
                func.sum(Sale.total_amount).label('revenue'),
                func.sum(Sale.total_cost).label('cogs')
            )
            .where(Sale.business_date >= start_date)
            .where(Sale.business_date <= end_date)
            .group_by(Sale.business_date)
            .order_by(Sale.business_date.asc())
        )
        sales_result = await db.execute(sales_query)
        sales_rows = sales_result.all()
        
        # Map sales data by date
        sales_map = {row.business_date: row for row in sales_rows}

        # 2. Query OPEX (Finance Ledger)
        from app.models.finance_ledger import FinanceLedger
        opex_query = (
            select(
                FinanceLedger.business_date,
                func.sum(FinanceLedger.amount).label('opex')
            )
            .where(FinanceLedger.business_date >= start_date)
            .where(FinanceLedger.business_date <= end_date)
            .group_by(FinanceLedger.business_date)
        )
        opex_result = await db.execute(opex_query)
        opex_map = {row.business_date: row.opex for row in opex_result.all()}

        # 3. Handle empty results
        if not sales_rows and not opex_map:
            return {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "line_chart": None,
                "data": [],
                "summary": {
                    "total_revenue": "0.00",
                    "total_cogs": "0.00",
                    "total_gross_profit": "0.00",
                    "total_opex": "0.00",
                    "total_net_profit": "0.00",
                    "avg_daily_revenue": "0.00",
                    "days_count": 0
                }
            }
        
        # 4. Build aggregated data points
        # Iterate through date range to ensure continuity? Or just available data?
        # For now, union of keys from sales and opex
        all_dates = sorted(set(list(sales_map.keys()) + list(opex_map.keys())))
        
        data = []
        total_revenue = Decimal("0")
        total_cogs = Decimal("0")
        total_opex = Decimal("0")
        
        # Prepare lists for chart
        chart_dates = []
        revenues_float = []
        cogs_float = []
        
        for d in all_dates:
            # Sales Data
            sales_row = sales_map.get(d)
            revenue = Decimal(str(sales_row.revenue)) if sales_row else Decimal("0")
            cogs = Decimal(str(sales_row.cogs)) if sales_row else Decimal("0")
            
            # OPEX Data
            opex_val = opex_map.get(d)
            opex = Decimal(str(opex_val)) if opex_val else Decimal("0")
            
            # Derived Metrics
            gross_profit = revenue - cogs
            net_profit = gross_profit - opex
            
            margin_percent = (
                (gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))
                if revenue > Decimal("0") else Decimal("0")
            )
            
            # Accumulate Totals
            total_revenue += revenue
            total_cogs += cogs
            total_opex += opex
            
            data.append({
                "business_date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                "revenue": str(revenue.quantize(Decimal("0.01"))),
                "cogs": str(cogs.quantize(Decimal("0.01"))),
                "gross_profit": str(gross_profit.quantize(Decimal("0.01"))),
                "margin_percent": str(margin_percent),
                "opex": str(opex.quantize(Decimal("0.01"))),
                "net_profit": str(net_profit.quantize(Decimal("0.01")))
            })
            
            chart_dates.append(d)
            revenues_float.append(float(revenue))
            cogs_float.append(float(cogs))
        
        # 5. Calculate summary
        days_count = len(all_dates)
        total_gross_profit = total_revenue - total_cogs
        total_net_profit = total_gross_profit - total_opex
        
        avg_daily_revenue = (
            (total_revenue / Decimal(str(days_count))).quantize(Decimal("0.01"))
            if days_count > 0 else Decimal("0")
        )
        
        summary = {
            "total_revenue": str(total_revenue.quantize(Decimal("0.01"))),
            "total_cogs": str(total_cogs.quantize(Decimal("0.01"))),
            "total_gross_profit": str(total_gross_profit.quantize(Decimal("0.01"))),
            "total_opex": str(total_opex.quantize(Decimal("0.01"))),
            "total_net_profit": str(total_net_profit.quantize(Decimal("0.01"))),
            "avg_daily_revenue": str(avg_daily_revenue),
            "days_count": days_count
        }
        
        # 6. Generate line chart
        line_chart = ProductSalesChartService._create_line_chart(
            dates=chart_dates,
            revenues=revenues_float,
            cogs=cogs_float
        )
        
        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "line_chart": line_chart,
            "data": data,
            "summary": summary
        }

    @staticmethod
    def _create_line_chart(
        dates: List[date],
        revenues: List[float],
        cogs: List[float]
    ) -> str:
        """
        Create a line chart showing Revenue vs COGS trend.
        
        Args:
            dates: List of business dates
            revenues: List of daily revenue values
            cogs: List of daily COGS values
            
        Returns:
            Base64-encoded PNG string
        """
        plt.figure(figsize=(14, 7))
        
        # Format dates for x-axis
        date_labels = [d.strftime('%d.%m') for d in dates]
        x_positions = range(len(dates))
        
        # Plot Revenue line (blue, solid)
        plt.plot(
            x_positions,
            revenues,
            color='#4A90E2',
            linewidth=2.5,
            marker='o',
            markersize=6,
            label='Выручка',
            linestyle='-'
        )
        
        # Plot COGS line (red, dashed)
        plt.plot(
            x_positions,
            cogs,
            color='#E74C3C',
            linewidth=2.5,
            marker='s',
            markersize=5,
            label='Себестоимость (COGS)',
            linestyle='--'
        )
        
        # Fill area between lines (profit zone)
        plt.fill_between(
            x_positions,
            cogs,
            revenues,
            alpha=0.2,
            color='#50C878',
            label='Валовая прибыль'
        )
        
        # Styling
        plt.xlabel('Дата', fontsize=12, fontweight='bold')
        plt.ylabel('Сумма (₸)', fontsize=12, fontweight='bold')
        plt.title(
            'Тренд продаж: Выручка vs Себестоимость',
            fontsize=14,
            fontweight='bold',
            pad=15
        )
        
        # X-axis labels
        if len(dates) <= 15:
            plt.xticks(x_positions, date_labels, rotation=45, ha='right', fontsize=9)
        else:
            # Show every Nth label to avoid crowding
            step = max(1, len(dates) // 15)
            plt.xticks(
                x_positions[::step],
                [date_labels[i] for i in range(0, len(date_labels), step)],
                rotation=45,
                ha='right',
                fontsize=9
            )
        
        plt.yticks(fontsize=10)
        
        # Grid
        plt.grid(True, alpha=0.3, linestyle='--')
        
        # Legend
        plt.legend(
            loc='upper right',
            fontsize=10,
            framealpha=0.9,
            edgecolor='gray'
        )
        
        # Remove top and right spines
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        
        # Format y-axis with thousands separator
        plt.gca().yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f'{x:,.0f}')
        )
        
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return img_base64
    @staticmethod
    async def get_ingredient_usage_chart(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Get multi-line chart for top ingredients usage over time.
        
        Args:
            db: Async database session
            start_date: Start date
            end_date: End date
            limit: Number of top ingredients (default 5)
            
        Returns:
            Dict containing data for Plotly.
        """
        from app.models.inventory_ledger import InventoryLedger
        from app.models.ingredient import Ingredient
        import uuid as uuid_mod
        
        # 1. Identify Top N ingredients by total cost in period
        subquery = (
            select(
                InventoryLedger.ingredient_id,
                func.sum(InventoryLedger.cost_snapshot).label('total_cost')
            )
            .where(InventoryLedger.event_type == 'SALE')
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
            .group_by(InventoryLedger.ingredient_id)
            .order_by(func.sum(InventoryLedger.cost_snapshot).desc())
            .limit(limit)
        ).subquery()
        
        # Get their names
        top_ingredients_result = await db.execute(
            select(Ingredient.id, Ingredient.name)
            .join(subquery, subquery.c.ingredient_id == Ingredient.id)
        )
        top_ingredients = {str(r.id): r.name for r in top_ingredients_result.all()}
        
        if not top_ingredients:
            return {"data": []}
            
        # 2. Get daily usage for these ingredients
        daily_query = (
            select(
                InventoryLedger.business_date,
                InventoryLedger.ingredient_id,
                func.sum(InventoryLedger.cost_snapshot).label('daily_cost')
            )
            .where(InventoryLedger.ingredient_id.in_([uuid_mod.UUID(uid) for uid in top_ingredients.keys()]))
            .where(InventoryLedger.event_type == 'SALE')
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
            .group_by(InventoryLedger.business_date, InventoryLedger.ingredient_id)
            .order_by(InventoryLedger.business_date)
        )
        
        result = await db.execute(daily_query)
        rows = result.all()
        
        # 3. Structure data for Plotly
        # Format: { "Ingredient A": { "2026-02-01": 100, ... }, ... }
        structured_data = {name: {} for name in top_ingredients.values()}
        
        # Initialize all dates with 0 for all top ingredients to ensure continuous lines
        from datetime import timedelta
        delta = end_date - start_date
        all_dates = [(start_date + timedelta(days=i)).isoformat() for i in range(delta.days + 1)]
        
        for name in top_ingredients.values():
            for d in all_dates:
                structured_data[name][d] = 0.0
                
        for row in rows:
            name = top_ingredients[str(row.ingredient_id)]
            date_str = row.business_date.isoformat()
            cost = float(row.daily_cost)
            structured_data[name][date_str] = cost
            
        # Convert to list for frontend
        chart_data = []
        for name, dates_map in structured_data.items():
            chart_data.append({
                "name": name,
                "dates": list(dates_map.keys()),
                "values": list(dates_map.values())
            })
            
        return {"data": chart_data}
