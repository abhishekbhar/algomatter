"""add RLS policies

Revision ID: aa8fa5c74ed6
Revises: d0e36e5a6fdb
Create Date: 2026-03-25 21:10:50.104941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa8fa5c74ed6'
down_revision: Union[str, None] = 'd0e36e5a6fdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RLS_TABLES = [
    "broker_connections",
    "strategies",
    "webhook_signals",
    "strategy_results",
    "paper_trading_sessions",
    "paper_positions",
    "paper_trades",
]


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant_id')::UUID)"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
