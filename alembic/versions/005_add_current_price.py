"""add current_price to ingredients

Revision ID: 005
Revises: 20260212_1331_857f110d7dec_add_fixed_cost_settings
Create Date: 2026-02-27

current_price — текущая цена за единицу (г/мл/шт).
Обновляется вручную в разделе "Цены сырья".
Используется для расчёта себестоимости продуктов.
Приоритет: current_price > WAC из ledger > initial_cost
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '20260212_1331_857f110d7dec_add_fixed_cost_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ingredients', sa.Column('current_price', sa.Numeric(10, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('ingredients', 'current_price')
