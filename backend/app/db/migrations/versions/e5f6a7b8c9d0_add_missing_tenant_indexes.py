"""add_missing_tenant_indexes

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-04-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_strategies_tenant_id", "strategies", ["tenant_id"])
    op.create_index("ix_paper_trading_sessions_tenant_id", "paper_trading_sessions", ["tenant_id"])
    op.create_index("ix_paper_positions_tenant_id", "paper_positions", ["tenant_id"])
    op.create_index("ix_paper_positions_session_symbol", "paper_positions", ["session_id", "symbol"])
    op.create_index("ix_webhook_signals_strategy_received", "webhook_signals", ["tenant_id", "strategy_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_strategies_tenant_id", table_name="strategies")
    op.drop_index("ix_paper_trading_sessions_tenant_id", table_name="paper_trading_sessions")
    op.drop_index("ix_paper_positions_tenant_id", table_name="paper_positions")
    op.drop_index("ix_paper_positions_session_symbol", table_name="paper_positions")
    op.drop_index("ix_webhook_signals_strategy_received", table_name="webhook_signals")
