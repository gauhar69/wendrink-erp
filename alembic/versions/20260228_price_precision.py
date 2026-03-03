"""increase_price_precision

Revision ID: 20260228_price_precision
Revises: 857f110d7dec
Create Date: 2026-02-28 12:00:00

Увеличиваем точность хранения цены с 4 до 8 знаков после запятой.
Причина: 56000 / 24000 = 2.3333 (4 знака) → 2.3333 × 24000 = 55999.2 → показывает 55999 вместо 56000.
С 8 знаками: 2.33333333 × 24000 = 55999.9992 → округляет до 56000 ✓
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260228_price_precision'
down_revision: Union[str, None] = '857f110d7dec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ingredients') as batch_op:
        batch_op.alter_column(
            'current_price',
            existing_type=sa.Numeric(10, 4),
            type_=sa.Numeric(14, 8),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'initial_cost',
            existing_type=sa.Numeric(10, 4),
            type_=sa.Numeric(14, 8),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('ingredients') as batch_op:
        batch_op.alter_column(
            'current_price',
            existing_type=sa.Numeric(14, 8),
            type_=sa.Numeric(10, 4),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'initial_cost',
            existing_type=sa.Numeric(14, 8),
            type_=sa.Numeric(10, 4),
            existing_nullable=True,
        )
