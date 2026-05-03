"""add adjustments_applied_at to stocktakes for /reapply idempotency

Revision ID: reapply_idem
Revises: 005
Create Date: 2026-05-03

PATCH 2.2: предотвращает повторное применение коррекций инвентаризации
при многократных вызовах endpoint POST /api/stocktake/{id}/reapply.

Backfill: всем уже завершённым stocktake выставляет
adjustments_applied_at = completed_at, потому что коррекции для
них уже применены (это происходит в complete_stocktake).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'reapply_idem'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: проверяем что колонки ещё нет
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('stocktakes')]

    if 'adjustments_applied_at' not in columns:
        with op.batch_alter_table('stocktakes') as batch_op:
            batch_op.add_column(sa.Column(
                'adjustments_applied_at',
                sa.DateTime(timezone=True),
                nullable=True,
            ))

    # Бэкфил: для всех уже завершённых стоктейков коррекции были применены
    # внутри complete_stocktake → ставим timestamp = completed_at,
    # чтобы /reapply на них не сработал случайно ещё раз.
    op.execute("""
        UPDATE stocktakes
        SET adjustments_applied_at = completed_at
        WHERE status = 'completed' AND completed_at IS NOT NULL
    """)


def downgrade() -> None:
    with op.batch_alter_table('stocktakes') as batch_op:
        batch_op.drop_column('adjustments_applied_at')
