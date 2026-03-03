"""Add package_size to ingredients

Revision ID: 003
Revises: 002_add_payroll_fields
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_package_size'
down_revision: Union[str, None] = '002_add_payroll_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add package_size column to ingredients table.
    
    This field stores the number of base units (grams/ml) per package.
    Example: '3KG * 8 packs' = 24000 grams per box
    
    Default is 1.0 for items that are already measured in base units.
    """
    op.add_column(
        'ingredients',
        sa.Column(
            'package_size',
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            server_default='1.0',
        )
    )


def downgrade() -> None:
    """Remove package_size column from ingredients table."""
    op.drop_column('ingredients', 'package_size')
