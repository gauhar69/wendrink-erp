"""Add stocktake tables

Revision ID: 004
Revises: 003_add_package_size
Create Date: 2026-02-07

Таблицы для проведения инвентаризации:
- stocktakes: основная инвентаризация
- stocktake_items: позиции (по каждому ингредиенту)

Law 1: LEDGER-FIRST
При завершении инвентаризации создаются ADJUSTMENT события в ledger.
Мы НЕ храним current_stock — остаток всегда SUM(ledger).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003_add_package_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create stocktakes table
    op.create_table(
        "stocktakes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("conducted_by", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_expected_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_actual_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_variance_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create stocktake_items table
    op.create_table(
        "stocktake_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "stocktake_id",
            sa.String(36),
            sa.ForeignKey("stocktakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.String(36),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("expected_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("variance_quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("unit_cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("variance_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    
    # Create indexes for better query performance
    op.create_index(
        "ix_stocktakes_business_date",
        "stocktakes",
        ["business_date"],
    )
    op.create_index(
        "ix_stocktake_items_stocktake_id",
        "stocktake_items",
        ["stocktake_id"],
    )
    op.create_index(
        "ix_stocktake_items_ingredient_id",
        "stocktake_items",
        ["ingredient_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stocktake_items_ingredient_id", "stocktake_items")
    op.drop_index("ix_stocktake_items_stocktake_id", "stocktake_items")
    op.drop_index("ix_stocktakes_business_date", "stocktakes")
    op.drop_table("stocktake_items")
    op.drop_table("stocktakes")
