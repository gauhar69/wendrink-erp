"""
WENDRINK ERP - Main API Router

Aggregates all API routes.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.ingredients import router as ingredients_router
from app.api.inventory import router as inventory_router
from app.api.products import router as products_router
from app.api.recipes import router as recipes_router
from app.api.sales import router as sales_router
from app.api.finance import router as finance_router
from app.api.reports import router as reports_router
from app.api.charts import router as charts_router
from app.api.data_import import router as data_import_router
from app.api.analytics import router as analytics_router
from app.api.stocktake import router as stocktake_router
from app.api.verification import router as verification_router

# Main API router
api_router = APIRouter()

# Auth routes (must be first, and open — no auth required)
api_router.include_router(auth_router)

# Include sub-routers
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(ingredients_router, prefix="/ingredients", tags=["Ingredients"])
api_router.include_router(products_router, prefix="/products", tags=["Products"])
api_router.include_router(recipes_router, prefix="/recipes", tags=["Recipes"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(sales_router, prefix="/sales", tags=["Sales"])
api_router.include_router(finance_router, prefix="/finance", tags=["Finance", "OPEX", "Payroll"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports", "P&L", "Analytics"])
api_router.include_router(charts_router, prefix="/charts", tags=["Charts"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics", "Forecast"])
api_router.include_router(stocktake_router, prefix="/stocktake", tags=["Stocktake", "Inventory Check"])
api_router.include_router(data_import_router, prefix="/data-import", tags=["Data Import"])
api_router.include_router(verification_router) # Auto-prefixed in module

