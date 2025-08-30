"""Add Jobs, Backtests (skeleton), and Config tables

Revision ID: add_jobs_backtests_config_001
Revises: c91def111127
Create Date: 2025-08-30 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_jobs_backtests_config_001'
down_revision = 'c91def111127'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Jobs table to track mode/phase runs
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_type', sa.String(50), nullable=False),  # mining|backtest|optimize|trading
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.String(500), nullable=True),
    )
    op.create_index('ix_jobs_type_status', 'jobs', ['job_type', 'status'])

    # Backtests skeleton table
    op.create_table(
        'backtests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_id', sa.String(100), nullable=False),
        sa.Column('symbols', sa.JSON(), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.String(500), nullable=True),
    )
    op.create_index('ix_backtests_strategy_status', 'backtests', ['strategy_id', 'status'])

    # Config key-value table
    op.create_table(
        'config',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('config')
    op.drop_index('ix_backtests_strategy_status', table_name='backtests')
    op.drop_table('backtests')
    op.drop_index('ix_jobs_type_status', table_name='jobs')
    op.drop_table('jobs')

