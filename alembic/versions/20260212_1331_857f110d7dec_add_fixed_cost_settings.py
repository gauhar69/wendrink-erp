"""add_fixed_cost_settings

Revision ID: 857f110d7dec
Revises: 004
Create Date: 2026-02-12 13:31:13.554663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '857f110d7dec'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Проверяем существование таблицы перед созданием (idempotent)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'fixed_cost_settings' not in inspector.get_table_names():
        op.create_table('fixed_cost_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('category_name', sa.String(length=100), nullable=False, comment="Name of the expense (e.g., 'Аренда')"),
        sa.Column('monthly_amount', sa.Numeric(precision=12, scale=2), nullable=False, comment='Total monthly cost in KZT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='If False, this cost is ignored in calculations'),
        sa.Column('description', sa.Text(), nullable=True, comment='Optional notes'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_name')
        )


def downgrade() -> None:
    op.drop_table('fixed_cost_settings')
