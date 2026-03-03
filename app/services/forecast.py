"""
WENDRINK ERP - Inventory Forecast Service

Прогноз остатков ингредиентов на основе исторических данных.
Использует линейную регрессию для определения тренда.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import io
import base64

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ingredient, InventoryLedger, Sale, Product, Recipe
from app.models.sale import SaleItem


class InventoryForecastService:
    """Service for inventory forecasting and analytics."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_inventory_forecast(
        self,
        analysis_days: int = 7,
        forecast_days: int = 30,
    ) -> dict:
        """
        Get inventory forecast for all ingredients.
        
        Args:
            analysis_days: Days to analyze for trend (7-14)
            forecast_days: Days to forecast (30)
            
        Returns:
            Forecast data with charts
        """
        # Get all ingredients
        ingredients_query = select(Ingredient)
        result = await self.session.execute(ingredients_query)
        ingredients = result.scalars().all()
        
        # Get current date
        today = date.today()
        start_date = today - timedelta(days=analysis_days)
        
        # Get daily usage for each ingredient
        forecasts = []
        urgent_list = []
        soon_list = []
        ok_list = []
        
        for ingredient in ingredients:
            forecast = await self._forecast_ingredient(
                ingredient=ingredient,
                start_date=start_date,
                end_date=today,
                forecast_days=forecast_days,
            )
            
            if forecast:
                forecasts.append(forecast)
                
                # Categorize by urgency
                days_left = forecast["days_left"]
                if days_left is not None:
                    if days_left < 7:
                        urgent_list.append(forecast)
                    elif days_left < 14:
                        soon_list.append(forecast)
                    else:
                        ok_list.append(forecast)
        
        # Sort by days_left
        forecasts.sort(key=lambda x: x["days_left"] if x["days_left"] is not None else 9999)
        
        # Generate chart for top 10 urgent items
        chart_items = (urgent_list + soon_list)[:10]
        line_chart = await self._generate_forecast_chart(chart_items, forecast_days) if chart_items else None
        
        return {
            "status": "success",
            "analysis_date": str(today),
            "analysis_days": analysis_days,
            "forecast_days": forecast_days,
            "line_chart": line_chart,
            "forecasts": forecasts,
            "priority_list": {
                "urgent": urgent_list,
                "soon": soon_list,
                "ok": ok_list,
            },
            "summary": {
                "total_ingredients": len(ingredients),
                "urgent_count": len(urgent_list),
                "warning_count": len(soon_list),
                "ok_count": len(ok_list),
            }
        }
    
    async def _forecast_ingredient(
        self,
        ingredient: Ingredient,
        start_date: date,
        end_date: date,
        forecast_days: int,
    ) -> Optional[dict]:
        """Forecast single ingredient."""
        
        # Get current stock
        stock_query = select(func.sum(InventoryLedger.change_amount)).where(
            InventoryLedger.ingredient_id == ingredient.id
        )
        result = await self.session.execute(stock_query)
        current_stock = result.scalar() or Decimal("0")
        
        if current_stock <= 0:
            return None
        
        # Get daily usage from inventory_ledger (SALE events)
        usage_query = (
            select(
                InventoryLedger.business_date,
                func.sum(func.abs(InventoryLedger.change_amount)).label("usage")
            )
            .where(InventoryLedger.ingredient_id == ingredient.id)
            .where(InventoryLedger.event_type == "SALE")
            .where(InventoryLedger.business_date >= start_date)
            .where(InventoryLedger.business_date <= end_date)
            .group_by(InventoryLedger.business_date)
            .order_by(InventoryLedger.business_date)
        )
        
        result = await self.session.execute(usage_query)
        daily_usage = result.all()
        
        if not daily_usage:
            # No usage data - can't forecast
            return {
                "ingredient": ingredient.name,
                "ingredient_id": str(ingredient.id),
                "unit": ingredient.unit,
                "current_stock": str(current_stock),
                "daily_usage_avg": "0",
                "trend_percent": 0,
                "predicted_daily": "0",
                "days_left": None,
                "stockout_date": None,
                "order_by_date": None,
                "order_amount": "N/A",
                "status": "unknown",
                "message": "No usage data"
            }
        
        # Calculate average daily usage
        usage_values = [float(u.usage) for u in daily_usage]
        daily_avg = sum(usage_values) / len(usage_values)
        
        # Calculate trend using linear regression
        if len(usage_values) >= 3:
            x = np.arange(len(usage_values))
            y = np.array(usage_values)
            
            # Linear regression: y = mx + b
            coefficients = np.polyfit(x, y, 1)
            slope = coefficients[0]
            
            # Trend as percentage
            trend_percent = (slope / daily_avg * 100) if daily_avg > 0 else 0
            
            # Predict future daily usage
            future_x = len(usage_values) + forecast_days // 2
            predicted_daily = max(daily_avg + slope * (forecast_days // 2), daily_avg * 0.5)
        else:
            trend_percent = 0
            predicted_daily = daily_avg
        
        # Calculate days left
        if predicted_daily > 0:
            days_left = float(current_stock) / predicted_daily
        else:
            days_left = 9999  # Effectively infinite
        
        # Calculate stockout date
        if days_left < 9999:
            stockout_date = end_date + timedelta(days=int(days_left))
            order_by_date = stockout_date - timedelta(days=4)
        else:
            stockout_date = None
            order_by_date = None
        
        # Calculate order amount (30 days supply)
        order_amount_value = predicted_daily * 30
        
        # Convert to packages
        package_size = ingredient.package_size or 1
        packages_needed = int(order_amount_value / package_size) + 1
        order_amount = f"{packages_needed} уп."
        
        # Determine status
        if days_left < 7:
            status = "critical"
        elif days_left < 14:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "ingredient": ingredient.name,
            "ingredient_id": str(ingredient.id),
            "unit": ingredient.unit,
            "current_stock": str(round(float(current_stock), 1)),
            "daily_usage_avg": str(round(daily_avg, 1)),
            "trend_percent": round(trend_percent, 1),
            "predicted_daily": str(round(predicted_daily, 1)),
            "days_left": round(days_left, 1) if days_left < 9999 else None,
            "stockout_date": str(stockout_date) if stockout_date else None,
            "order_by_date": str(order_by_date) if order_by_date else None,
            "order_amount": order_amount,
            "status": status,
        }
    
    async def _generate_forecast_chart(
        self,
        forecasts: list,
        forecast_days: int,
    ) -> Optional[str]:
        """Generate line chart for inventory forecast."""
        
        if not forecasts:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        today = date.today()
        dates = [today + timedelta(days=i) for i in range(forecast_days + 1)]
        
        colors = {
            "critical": "red",
            "warning": "orange",
            "ok": "green",
        }
        
        for forecast in forecasts[:5]:  # Top 5
            name = forecast["ingredient"][:15]
            current = float(forecast["current_stock"])
            daily = float(forecast["predicted_daily"]) if forecast["predicted_daily"] != "0" else 0
            
            if daily > 0:
                values = [max(0, current - daily * i) for i in range(forecast_days + 1)]
                color = colors.get(forecast["status"], "blue")
                ax.plot(dates, values, label=name, color=color, linewidth=2)
        
        # Critical zone
        ax.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Критический уровень')
        
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Остаток', fontsize=12)
        ax.set_title('Прогноз остатков ингредиентов', fontsize=14, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        # Format dates
        ax.xaxis.set_major_formatter(DateFormatter('%d.%m'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return chart_base64
    
    async def get_inventory_status(self) -> dict:
        """Get current inventory status grouped by level."""
        
        # Get all ingredients with stock
        query = (
            select(
                Ingredient.id,
                Ingredient.name,
                Ingredient.unit,
                func.sum(InventoryLedger.change_amount).label("stock")
            )
            .join(InventoryLedger, InventoryLedger.ingredient_id == Ingredient.id)
            .group_by(Ingredient.id, Ingredient.name, Ingredient.unit)
            .order_by(func.sum(InventoryLedger.change_amount).asc())
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        critical = []
        warning = []
        ok = []
        
        for row in rows:
            stock = float(row.stock) if row.stock else 0
            
            item = {
                "ingredient_id": str(row.id),
                "ingredient": row.name,
                "unit": row.unit,
                "current_stock": round(stock, 1),
            }
            
            # Simple threshold based on stock level
            if stock < 500:
                item["status"] = "critical"
                critical.append(item)
            elif stock < 2000:
                item["status"] = "warning"
                warning.append(item)
            else:
                item["status"] = "ok"
                ok.append(item)
        
        # Generate bar chart
        bar_chart = await self._generate_status_chart(critical, warning, ok)
        
        return {
            "status": "success",
            "bar_chart": bar_chart,
            "data": {
                "critical": critical,
                "warning": warning,
                "ok": ok,
            },
            "summary": {
                "critical_count": len(critical),
                "warning_count": len(warning),
                "ok_count": len(ok),
            }
        }
    
    async def _generate_status_chart(
        self,
        critical: list,
        warning: list,
        ok: list,
    ) -> Optional[str]:
        """Generate horizontal bar chart for inventory status."""
        
        items = critical[:5] + warning[:5]  # Show only critical and warning
        
        if not items:
            return None
        
        fig, ax = plt.subplots(figsize=(10, max(4, len(items) * 0.5)))
        
        names = [i["ingredient"][:20] for i in items]
        values = [i["current_stock"] for i in items]
        colors = ["red" if i["status"] == "critical" else "orange" for i in items]
        
        y_pos = range(len(names))
        ax.barh(y_pos, values, color=colors)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel('Остаток')
        ax.set_title('Критические и низкие остатки', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return chart_base64
    
    async def get_category_sales(self, business_date: date) -> dict:
        """Get sales breakdown by product category."""
        
        # Query sales grouped by product
        query = (
            select(
                Product.name,
                func.sum(SaleItem.quantity).label("qty"),
                func.sum(SaleItem.unit_price * SaleItem.quantity).label("revenue")
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.business_date == business_date)
            .group_by(Product.name)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Group by category based on product name patterns
        categories = {
            "Мороженое": Decimal("0"),
            "Молочные чаи": Decimal("0"),
            "Фруктовые чаи": Decimal("0"),
            "Кофе": Decimal("0"),
            "Вафли": Decimal("0"),
            "Допы": Decimal("0"),
            "Прочее": Decimal("0"),
        }
        
        def get_category(name: str) -> str:
            name_lower = name.lower()
            if any(x in name_lower for x in ["рожок", "сандэ", "мороженое", "софт"]):
                return "Мороженое"
            elif any(x in name_lower for x in ["молочный чай", "матча латте", "таро", "орео"]):
                return "Молочные чаи"
            elif any(x in name_lower for x in ["фруктовый", "манго", "клубника", "маракуйя"]):
                return "Фруктовые чаи"
            elif any(x in name_lower for x in ["кофе", "амер", "латте", "капучино", "раф"]):
                return "Кофе"
            elif any(x in name_lower for x in ["вафл", "waffle"]):
                return "Вафли"
            elif any(x in name_lower for x in ["доп", "тапиок", "карамел", "сироп"]):
                return "Допы"
            else:
                return "Прочее"
        
        total_revenue = Decimal("0")
        
        for row in rows:
            name = row.name or "Unknown"
            revenue = Decimal(str(row.revenue)) if row.revenue else Decimal("0")
            total_revenue += revenue
            
            category = get_category(name)
            categories[category] += revenue
        
        # Build response data
        data = []
        for cat_name, revenue in categories.items():
            if revenue > 0:
                pct = (revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")
                data.append({
                    "category": cat_name,
                    "revenue": str(revenue),
                    "percentage": round(float(pct), 1),
                    "products_count": 0,  # Simplified
                })
        
        # Sort by revenue desc
        data.sort(key=lambda x: float(x["revenue"]), reverse=True)
        
        # Generate charts
        bar_chart, pie_chart = await self._generate_category_charts(data)
        
        return {
            "status": "success",
            "business_date": str(business_date),
            "bar_chart": bar_chart,
            "pie_chart": pie_chart,
            "data": data,
            "total_revenue": str(total_revenue),
        }
    
    async def _generate_category_charts(self, data: list) -> tuple:
        """Generate bar and pie charts for categories."""
        
        if not data:
            return None, None
        
        categories = [d["category"] for d in data]
        revenues = [float(d["revenue"]) for d in data]
        
        # Bar chart
        fig1, ax1 = plt.subplots(figsize=(10, 5))
        colors = plt.cm.Set3(range(len(categories)))
        ax1.bar(categories, revenues, color=colors)
        ax1.set_ylabel('Выручка (₸)')
        ax1.set_title('Выручка по категориям', fontsize=14, fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        ax1.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        
        buf1 = io.BytesIO()
        plt.savefig(buf1, format='png', dpi=100)
        buf1.seek(0)
        bar_chart = base64.b64encode(buf1.read()).decode('utf-8')
        plt.close(fig1)
        
        # Pie chart
        fig2, ax2 = plt.subplots(figsize=(8, 8))
        ax2.pie(revenues, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
        ax2.set_title('Доля в выручке', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        buf2 = io.BytesIO()
        plt.savefig(buf2, format='png', dpi=100)
        buf2.seek(0)
        pie_chart = base64.b64encode(buf2.read()).decode('utf-8')
        plt.close(fig2)
        
        return bar_chart, pie_chart
