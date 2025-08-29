"""Create market data tables

Revision ID: market_data_001
Revises: c91def111127
Create Date: 2025-08-28 07:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'market_data_001'
down_revision = 'c91def111127'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create candles_1min table
    op.create_table('candles_1min',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'timestamp', name='uq_symbol_timestamp')
    )
    op.create_index('idx_symbol_timestamp', 'candles_1min', ['symbol', 'timestamp'])
    op.create_index('idx_timestamp', 'candles_1min', ['timestamp'])
    
    # Create mining_status table
    op.create_table('mining_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('first_date', sa.DateTime(timezone=True)),
        sa.Column('last_date', sa.DateTime(timezone=True)),
        sa.Column('total_candles', sa.Integer(), default=0),
        sa.Column('gaps_detected', sa.Integer(), default=0),
        sa.Column('last_update', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('data_quality_score', sa.Float(), default=0.0),
        sa.Column('phase', sa.Integer(), default=1),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', name='uq_mining_symbol')
    )
    op.create_index('idx_symbol_active', 'mining_status', ['symbol', 'is_active'])
    
    # Create mining_logs table
    op.create_table('mining_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True)),
        sa.Column('candles_added', sa.Integer(), default=0),
        sa.Column('success', sa.Boolean(), default=False),
        sa.Column('error_message', sa.String(500)),
        sa.Column('api_calls', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_symbol_operation', 'mining_logs', ['symbol', 'operation'])
    op.create_index('idx_created_at', 'mining_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('mining_logs')
    op.drop_table('mining_status')
    op.drop_table('candles_1min')