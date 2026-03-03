"""Initial schema - WENDRINK ERP

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-27

Creates all core tables:
- ingredients
- products
- recipes
- inventory_ledger (APPEND-ONLY)
- finance_ledger (APPEND-ONLY)
- sales
- sale_items
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === INGREDIENTS ===
    op.create_table(
        'ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False, comment='Unit of measurement: kg, l, pcs'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ingredients_name', 'ingredients', ['name'], unique=True)

    # === PRODUCTS ===
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False, comment='Selling price in KZT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_products_name', 'products', ['name'], unique=True)

    # === RECIPES ===
    op.create_table(
        'recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False, comment='Quantity of ingredient needed per 1 product unit'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('product_id', 'ingredient_id', name='uq_recipe_product_ingredient'),
    )
    op.create_index('ix_recipes_product_id', 'recipes', ['product_id'])
    op.create_index('ix_recipes_ingredient_id', 'recipes', ['ingredient_id'])

    # === INVENTORY LEDGER (APPEND-ONLY) ===
    op.create_table(
        'inventory_ledger',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False, comment='SUPPLY, SALE, CORRECTION, ADJUSTMENT'),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Reference to original event for CORRECTION entries'),
        sa.Column('change_amount', sa.Numeric(10, 4), nullable=False, comment='Positive for incoming, negative for outgoing'),
        sa.Column('unit_cost', sa.Numeric(12, 4), nullable=True, comment='Cost per unit for SUPPLY events'),
        sa.Column('weighted_average_cost', sa.Numeric(12, 4), nullable=False, comment='WAC calculated at event time'),
        sa.Column('cost_snapshot', sa.Numeric(12, 4), nullable=False, comment='IMMUTABLE: abs(change_amount) * WAC at event time'),
        sa.Column('negative_stock', sa.Boolean(), nullable=False, server_default='false', comment='True if this event caused stock to go negative'),
        sa.Column('reason', sa.Text(), nullable=True, comment='Explanation for CORRECTION/ADJUSTMENT events'),
        sa.Column('business_date', sa.Date(), nullable=False, comment='Almaty business date (06:00 cutoff)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_inventory_ledger_ingredient_id', 'inventory_ledger', ['ingredient_id'])
    op.create_index('ix_inventory_ledger_event_type', 'inventory_ledger', ['event_type'])
    op.create_index('ix_inventory_ledger_business_date', 'inventory_ledger', ['business_date'])

    # === FINANCE LEDGER (APPEND-ONLY) ===
    op.create_table(
        'finance_ledger',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, comment='SALARY, RENT, UTILITIES, etc.'),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, comment='Amount in KZT (positive for expense)'),
        sa.Column('description', sa.Text(), nullable=True, comment='Additional details about the expense'),
        sa.Column('business_date', sa.Date(), nullable=False, comment='Almaty business date for P&L allocation'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_finance_ledger_category', 'finance_ledger', ['category'])
    op.create_index('ix_finance_ledger_business_date', 'finance_ledger', ['business_date'])

    # === SALES ===
    op.create_table(
        'sales',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, comment='Total sale amount (revenue) in KZT'),
        sa.Column('total_cost', sa.Numeric(12, 4), nullable=False, comment='IMMUTABLE: Total COGS at sale time'),
        sa.Column('business_date', sa.Date(), nullable=False, comment='Almaty business date (06:00 cutoff)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_business_date', 'sales', ['business_date'])

    # === SALE ITEMS ===
    op.create_table(
        'sale_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sale_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, comment='Number of units sold'),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=False, comment='IMMUTABLE: Price per unit at sale time'),
        sa.Column('line_total', sa.Numeric(12, 2), nullable=False, comment='quantity * unit_price'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_sale_items_sale_id', 'sale_items', ['sale_id'])
    op.create_index('ix_sale_items_product_id', 'sale_items', ['product_id'])


def downgrade() -> None:
    op.drop_table('sale_items')
    op.drop_table('sales')
    op.drop_table('finance_ledger')
    op.drop_table('inventory_ledger')
    op.drop_table('recipes')
    op.drop_table('products')
    op.drop_table('ingredients')
