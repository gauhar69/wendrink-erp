
"""
Data Seeding Script for WENDRINK ERP.
Populates the database with initial data:
- Ingredients (Inventory Items)
- Products (Menu Items)
- Recipes (Tech Cards)
- Initial Supply (Stock)
- Initial Sales (History)
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe import Recipe
from app.services.inventory import InventoryService
from app.services.sale import SaleService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DATA DEFINITIONS ---

INGREDIENTS_DATA = [
     {"name": "Ориг. порошок мороженое (1кг*20)", "sku": "ING-001", "unit": "гр", "package_size": 20000},
     {"name": "Рожок (Вафельный) (600шт)", "sku": "ING-002", "unit": "шт", "package_size": 600},
     {"name": "Шоколадный соус (2.5кг*6)", "sku": "ING-003", "unit": "гр", "package_size": 15000},
     {"name": "Клубничный джем (2.5кг*6)", "sku": "ING-004", "unit": "гр", "package_size": 15000},
     {"name": "Улун чай (500гр*30)", "sku": "ING-005", "unit": "гр", "package_size": 15000},
     {"name": "Черный чай (500гр*30)", "sku": "ING-006", "unit": "гр", "package_size": 15000},
     {"name": "Жасминовый чай (500гр*30)", "sku": "ING-007", "unit": "гр", "package_size": 15000},
     {"name": "Сахарный сироп (Самодел)", "sku": "ING-008", "unit": "мл", "package_size": 1000},
     {"name": "Тапиока (1кг*20)", "sku": "ING-009", "unit": "гр", "package_size": 20000},
     {"name": "Сухое молоко (1кг*25)", "sku": "ING-010", "unit": "гр", "package_size": 25000},
     {"name": "Сгущенка (380гр*30)", "sku": "ING-011", "unit": "гр", "package_size": 11400},
     {"name": "Кофе зерновой (1кг)", "sku": "ING-012", "unit": "гр", "package_size": 1000},
     {"name": "Молоко 3.2% (1л)", "sku": "ING-013", "unit": "мл", "package_size": 1000},
     {"name": "Стакан 350мл (100шт)", "sku": "ING-014", "unit": "шт", "package_size": 100},
     {"name": "Стакан 500мл (100шт)", "sku": "ING-015", "unit": "шт", "package_size": 100},
     {"name": "Крышка купол (100шт)", "sku": "ING-016", "unit": "шт", "package_size": 100},
     {"name": "Трубочка широкая (100шт)", "sku": "ING-017", "unit": "шт", "package_size": 100},
     {"name": "Манго пюре (1кг*12)", "sku": "ING-018", "unit": "гр", "package_size": 12000},
     {"name": "Маракуйя пюре (1кг*12)", "sku": "ING-019", "unit": "гр", "package_size": 12000},
]

PRODUCTS_DATA = [
     {"name": "Рожок сливочный", "code": "P-001", "sale_price": "300"},
     {"name": "Сандэ Шоколадный", "code": "P-002", "sale_price": "650"},
     {"name": "Сандэ Клубничный", "code": "P-003", "sale_price": "650"},
     {"name": "Молочный чай Классик (M)", "code": "P-004", "sale_price": "650"},
     {"name": "Молочный чай Классик (L)", "code": "P-005", "sale_price": "800"},
     {"name": "Таро Молочный чай (M)", "code": "P-006", "sale_price": "900"},
     {"name": "Манго Фруктовый чай (L)", "code": "P-007", "sale_price": "850"},
     {"name": "Американо", "code": "P-008", "sale_price": "600"},
     {"name": "Капучино", "code": "P-009", "sale_price": "800"},
     {"name": "Латте", "code": "P-010", "sale_price": "900"},
]

# (Product Name, Ingredient Name, Quantity)
RECIPES_DATA = [
     ("Рожок сливочный", "Ориг. порошок мороженое (1кг*20)", 31),
     ("Рожок сливочный", "Рожок (Вафельный) (600шт)", 1),
     
     ("Сандэ Шоколадный", "Ориг. порошок мороженое (1кг*20)", 64),
     ("Сандэ Шоколадный", "Шоколадный соус (2.5кг*6)", 30),
     ("Сандэ Шоколадный", "Стакан 350мл (100шт)", 1),
     
     ("Сандэ Клубничный", "Ориг. порошок мороженое (1кг*20)", 64),
     ("Сандэ Клубничный", "Клубничный джем (2.5кг*6)", 30),
     ("Сандэ Клубничный", "Стакан 350мл (100шт)", 1),
     
     ("Молочный чай Классик (M)", "Черный чай (500гр*30)", 5),
     ("Молочный чай Классик (M)", "Сахарный сироп (Самодел)", 20),
     ("Молочный чай Классик (M)", "Сухое молоко (1кг*25)", 30),
     ("Молочный чай Классик (M)", "Тапиока (1кг*20)", 40),
     ("Молочный чай Классик (M)", "Стакан 500мл (100шт)", 1), # Using 500ml cup for M just for example
     ("Молочный чай Классик (M)", "Трубочка широкая (100шт)", 1),
     
     ("Капучино", "Кофе зерновой (1кг)", 18),
     ("Капучино", "Молоко 3.2% (1л)", 150),
     ("Капучино", "Сахарный сироп (Самодел)", 10),
     ("Капучино", "Стакан 350мл (100шт)", 1),
]

SUPPLY_DATA = [
     ("Ориг. порошок мороженое (1кг*20)", 50000, 56000), # 50kg, 56000 total (Wait, price per pack?)
                                                         # Let's assume quantity is in base units (grams) and total_cost is for that quantity
                                                         # Powder: 20kg pack cost? Let's check logic.
                                                         # Supply logic takes: quantity (base units), total_cost (total money)
     ("Рожок (Вафельный) (600шт)", 600, 4500), 
     ("Шоколадный соус (2.5кг*6)", 2500, 3800),
     ("Клубничный джем (2.5кг*6)", 2500, 3500),
     ("Черный чай (500гр*30)", 5000, 12000), 
     ("Сахарный сироп (Самодел)", 10000, 2000), 
     ("Тапиока (1кг*20)", 20000, 18000),
     ("Сухое молоко (1кг*25)", 25000, 32000),
     ("Кофе зерновой (1кг)", 5000, 25000),
     ("Молоко 3.2% (1л)", 20000, 8000),
     ("Стакан 350мл (100шт)", 500, 2500),
     ("Стакан 500мл (100шт)", 500, 3500),
     ("Трубочка широкая (100шт)", 1000, 1000),
]


async def seed_ingredients(session: AsyncSession):
    logger.info("Seeding ingredients...")
    for data in INGREDIENTS_DATA:
        stmt = select(Ingredient).where(Ingredient.name == data["name"])
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            ing = Ingredient(**data)
            session.add(ing)
    await session.commit()

async def seed_products(session: AsyncSession):
    logger.info("Seeding products...")
    for data in PRODUCTS_DATA:
        stmt = select(Product).where(Product.name == data["name"])
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            prod = Product(
                name=data["name"],
                sku=data["code"],  # Map code to sku
                price=Decimal(data["sale_price"])  # Map sale_price to price
            )
            session.add(prod)
    await session.commit()

async def seed_recipes(session: AsyncSession):
    logger.info("Seeding recipes...")
    for prod_name, ing_name, qty in RECIPES_DATA:
        # Get Product
        p_res = await session.execute(select(Product).where(Product.name == prod_name))
        product = p_res.scalar_one_or_none()
        
        # Get Ingredient
        i_res = await session.execute(select(Ingredient).where(Ingredient.name == ing_name))
        ingredient = i_res.scalar_one_or_none()
        
        if product and ingredient:
            # Check if recipe exists
            r_res = await session.execute(
                select(Recipe).where(
                    Recipe.product_id == product.id,
                    Recipe.ingredient_id == ingredient.id
                )
            )
            if not r_res.scalar_one_or_none():
                recipe = Recipe(
                    product_id=product.id,
                    ingredient_id=ingredient.id,
                    quantity=Decimal(str(qty))
                )
                session.add(recipe)
    await session.commit()

async def seed_supply(session: AsyncSession):
    logger.info("Seeding initial supply...")
    inv_service = InventoryService(session)
    yesterday = date.today() - timedelta(days=1)
    
    for ing_name, qty, cost in SUPPLY_DATA:
        i_res = await session.execute(select(Ingredient).where(Ingredient.name == ing_name))
        ingredient = i_res.scalar_one_or_none()
        
        if ingredient:
            # Check balance to avoid double seeding
            bal = await inv_service.get_stock_balance(ingredient.id)
            if bal == 0:
                await inv_service.record_supply(
                    ingredient_id=ingredient.id,
                    quantity=Decimal(qty),
                    total_cost=Decimal(cost),
                    business_date=yesterday
                )
    await session.commit()

from app.services.sale import SaleItemInput

async def seed_sales(session: AsyncSession):
    logger.info("Seeding fake sales history...")
    sale_service = SaleService(session)
    today = date.today()
    
    # 1. Sale: 5 Ice Creams
    p_res = await session.execute(select(Product).where(Product.name == "Рожок сливочный"))
    p_ice = p_res.scalar_one_or_none()
    
    if p_ice:
        logger.info(f"Found product for sale: {p_ice.name} ID={p_ice.id}")
        try:
            await sale_service.create_sale(
                items=[SaleItemInput(product_id=p_ice.id, quantity=5)],
                business_date=today
            )
            logger.info("Sale 1 created.")
        except Exception as e:
            logger.error(f"Failed to create Sale 1: {e}")

    # 2. Sale: 3 Cappuccinos
    p_res = await session.execute(select(Product).where(Product.name == "Капучино"))
    p_cap = p_res.scalar_one_or_none()
    
    if p_cap:
        logger.info(f"Found product for sale: {p_cap.name} ID={p_cap.id}")
        try:
            await sale_service.create_sale(
                items=[SaleItemInput(product_id=p_cap.id, quantity=3)],
                business_date=today
            )
            logger.info("Sale 2 created.")
        except Exception as e:
            logger.error(f"Failed to create Sale 2: {e}")
        
    await session.commit()


async def main():
    async with async_session_factory() as session:
        await seed_ingredients(session)
        await seed_products(session)
        await seed_recipes(session)
        await seed_supply(session)
    
    # Use a fresh session for sales to ensure clean state
    async with async_session_factory() as session:
        await seed_sales(session)
        
    logger.info("Seeding complete!")

if __name__ == "__main__":
    asyncio.run(main())
