"""add current_price to ingredients

Revision ID: 005
Revises: 857f110d7dec
Create Date: 2026-02-27

current_price — текущая цена за единицу (г/мл/шт).
Обновляется вручную в разделе "Цены сырья".
Используется для расчёта себестоимости продуктов.
Приоритет: current_price > WAC из ledger > initial_cost

FIX 2026-05-03: down_revision был ошибочно указан полным именем файла
('20260212_1331_857f110d7dec_add_fixed_cost_settings') вместо revision_id
('857f110d7dec'). Из-за этого alembic не мог построить revision_map,
и все миграции после 005 молча проглатывались RUN ... 2>/dev/null в
Dockerfile. БД зависла на '005' с февраля 2026.
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '857f110d7dec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ingredients', sa.Column('current_price', sa.Numeric(10, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('ingredients', 'current_price')
