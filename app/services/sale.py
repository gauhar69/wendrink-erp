"""
WENDRINK ERP - Sale Service

Handles sale transactions with atomic COGS capture.

LAWS ENFORCED:
- Law 2: Decimal Only
- Law 3: Cost Snapshot Immutable
- Law 5: Negative Stock Allowed
- Law 7: Atomic Transactions
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.recipe import Recipe
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.services.inventory import InventoryService
from app.utils.timezone import get_business_date


@dataclass
class SaleItemInput:
    """Input for a sale line item."""
    product_id: UUID
    quantity: int


@dataclass
class SaleResult:
    """Result of a sale transaction."""
    sale: Sale
    items: list[SaleItem]
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    negative_stock_warnings: list[str]


class SaleService:
    """
    Service for sale transactions.
    
    All sales are atomic - they either complete fully or roll back entirely.
    COGS is captured at sale time and never changes.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.inventory_service = InventoryService(session)
    
    async def create_sale(
        self,
        items: list[SaleItemInput],
        business_date: date | None = None,
    ) -> SaleResult:
        """
        Create a sale with atomic inventory deduction and COGS capture.
        
        Transaction Flow:
        1. Validate all products exist and have recipes
        2. For each item:
           a. Get product price (snapshot)
           b. For each recipe ingredient:
              i. Deduct from inventory
              ii. Capture COGS at current WAC
        3. Create sale header with totals
        4. Commit transaction
        
        Args:
            items: List of products and quantities to sell
            business_date: Business date (defaults to today)
            
        Returns:
            SaleResult with sale details and any warnings
            
        Raises:
            ValueError: If validation fails
        """
        if not items:
            raise ValueError("Sale must have at least one item")
        
        if business_date is None:
            business_date = get_business_date()
        
        # Validate all products and recipes upfront
        products_with_recipes = await self._validate_products(items)
        
        # Track totals
        total_revenue = Decimal("0")
        total_cogs = Decimal("0")
        negative_stock_warnings: list[str] = []
        sale_items: list[SaleItem] = []
        
        # Create sale header first (we'll update totals later)
        sale = Sale(
            total_amount=Decimal("0"),
            total_cost=Decimal("0"),
            business_date=business_date,
        )
        self.session.add(sale)
        await self.session.flush()  # Get sale.id
        
        # Process each item
        for item_input in items:
            product, recipes = products_with_recipes[item_input.product_id]
            
            # Snapshot product price at sale time
            unit_price = Decimal(str(product.price))
            line_total = unit_price * item_input.quantity
            total_revenue += line_total
            
            # Calculate COGS for this item (sum of ingredient costs)
            item_cogs = Decimal("0")
            
            for recipe in recipes:
                # Calculate how much ingredient we need
                ingredient_usage = Decimal(str(recipe.quantity)) * item_input.quantity
                
                # Deduct from inventory and get cost snapshot
                ledger_entry = await self.inventory_service.deduct_for_sale(
                    ingredient_id=recipe.ingredient_id,
                    quantity=ingredient_usage,
                    business_date=business_date,
                    sale_id=sale.id,  # Link to sale
                )
                
                # Accumulate COGS
                item_cogs += ledger_entry.cost_snapshot
                
                # Track negative stock warnings
                if ledger_entry.negative_stock:
                    ingredient_result = await self.session.execute(
                        select(Product).where(Product.id == recipe.ingredient_id)
                    )
                    # Get ingredient name for warning (graceful handling)
                    from app.models.ingredient import Ingredient
                    ing_result = await self.session.execute(
                        select(Ingredient).where(Ingredient.id == recipe.ingredient_id)
                    )
                    ingredient = ing_result.scalar_one_or_none()
                    ing_name = ingredient.name if ingredient else str(recipe.ingredient_id)
                    
                    negative_stock_warnings.append(
                        f"⚠ Negative stock: {ing_name}"
                    )
            
            total_cogs += item_cogs
            
            # Create sale item
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=item_input.quantity,
                unit_price=unit_price,
                line_total=line_total,
                total_cost=item_cogs,
            )
            self.session.add(sale_item)
            sale_items.append(sale_item)
        
        # Update sale totals
        sale.total_amount = total_revenue
        sale.total_cost = total_cogs
        
        await self.session.flush()
        
        return SaleResult(
            sale=sale,
            items=sale_items,
            total_revenue=total_revenue,
            total_cogs=total_cogs,
            gross_profit=total_revenue - total_cogs,
            negative_stock_warnings=negative_stock_warnings,
        )
    
    async def _validate_products(
        self,
        items: list[SaleItemInput],
    ) -> dict[UUID, tuple[Product, list[Recipe]]]:
        """
        Validate all products exist and have recipes.
        
        Returns:
            Dict mapping product_id to (Product, [Recipe]) tuple
            
        Raises:
            ValueError: If any product is invalid
        """
        result: dict[UUID, tuple[Product, list[Recipe]]] = {}
        
        for item in items:
            # Get product
            product_result = await self.session.execute(
                select(Product).where(Product.id == item.product_id)
            )
            product = product_result.scalar_one_or_none()
            
            if product is None:
                raise ValueError(f"Product {item.product_id} not found")
            
            if not product.is_active:
                raise ValueError(f"Product '{product.name}' is not active")
            
            if item.quantity <= 0:
                raise ValueError(f"Quantity must be positive for product '{product.name}'")
            
            # Get recipe
            recipe_result = await self.session.execute(
                select(Recipe).where(Recipe.product_id == item.product_id)
            )
            recipes = list(recipe_result.scalars().all())
            
            if not recipes:
                raise ValueError(f"Product '{product.name}' has no recipe defined")
            
            result[item.product_id] = (product, recipes)
        
        return result
    
    async def get_sale(self, sale_id: UUID) -> Sale | None:
        """Get a sale by ID with items."""
        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.items))
            .where(Sale.id == sale_id)
        )
        return result.scalar_one_or_none()
    
    async def get_sales(
        self,
        business_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Sale]:
        """Get sales with optional filters."""
        query = select(Sale).options(selectinload(Sale.items))
        
        if business_date:
            query = query.where(Sale.business_date == business_date)
        
        query = query.order_by(Sale.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_daily_summary(self, business_date: date) -> dict:
        """
        Get daily sales summary.
        
        Returns:
            Dict with revenue, cogs, gross_profit, margin, count
        """
        from sqlalchemy import func
        
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("revenue"),
                func.coalesce(func.sum(Sale.total_cost), Decimal("0")).label("cogs"),
                func.count(Sale.id).label("count"),
            )
            .where(Sale.business_date == business_date)
        )
        row = result.one()
        
        revenue = Decimal(str(row.revenue))
        cogs = Decimal(str(row.cogs))
        gross_profit = revenue - cogs
        margin = (gross_profit / revenue * 100) if revenue > 0 else Decimal("0")
        
        return {
            "business_date": business_date,
            "total_revenue": revenue,
            "total_cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_percent": margin,
            "transaction_count": row.count,
        }
