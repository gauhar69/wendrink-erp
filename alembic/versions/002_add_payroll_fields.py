"""Add payroll fields to finance_ledger

Revision ID: 002_add_payroll_fields
Revises: 001_initial_schema
Create Date: 2026-02-02T12:21:00

Phase 6.1: Daily Staff Payroll System
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_payroll_fields'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add payroll tracking fields to finance_ledger table."""
    
    # Add is_payroll boolean field
    op.add_column(
        'finance_ledger',
        sa.Column(
            'is_payroll',
            sa.Boolean(),
            nullable=True,  # Initially nullable for existing data
            comment='True if this is a daily staff payroll entry'
        )
    )
    
    # Add employee_breakdown JSON field
    op.add_column(
        'finance_ledger',
        sa.Column(
            'employee_breakdown',
            sa.JSON(),
            nullable=True,
            comment='JSON with employee payroll details: {employees: [...], total: ...}'
        )
    )
    
    # Add payroll_notes string field
    op.add_column(
        'finance_ledger',
        sa.Column(
            'payroll_notes',
            sa.String(500),
            nullable=True,
            comment='Additional notes about the payroll'
        )
    )
    
    # Update existing rows to have is_payroll = False
    op.execute("UPDATE finance_ledger SET is_payroll = 0 WHERE is_payroll IS NULL")
    
    # Make is_payroll non-nullable after updating existing data
    # Note: SQLite doesn't support ALTER COLUMN, so we use batch mode
    with op.batch_alter_table('finance_ledger') as batch_op:
        batch_op.alter_column(
            'is_payroll',
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )


def downgrade() -> None:
    """Remove payroll tracking fields from finance_ledger table."""
    
    with op.batch_alter_table('finance_ledger') as batch_op:
        batch_op.drop_column('payroll_notes')
        batch_op.drop_column('employee_breakdown')
        batch_op.drop_column('is_payroll')
