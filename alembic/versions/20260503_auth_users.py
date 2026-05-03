"""add_users_table

Revision ID: auth_users
Revises: reapply_idem
Create Date: 2026-05-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'auth_users'
down_revision: Union[str, None] = 'reapply_idem'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.CHAR(32), primary_key=True),
        sa.Column('login', sa.String(64), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(32), nullable=False, server_default='admin'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_login', 'users', ['login'])


def downgrade() -> None:
    op.drop_index('ix_users_login', table_name='users')
    op.drop_table('users')
