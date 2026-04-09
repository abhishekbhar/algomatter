"""broker_connection_cascade_delete

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # strategies.broker_connection_id → SET NULL on broker delete
    op.drop_constraint(
        "strategies_broker_connection_id_fkey", "strategies", type_="foreignkey"
    )
    op.create_foreign_key(
        "strategies_broker_connection_id_fkey",
        "strategies", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="SET NULL",
    )

    # strategy_deployments.broker_connection_id → CASCADE on broker delete
    op.drop_constraint(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="CASCADE",
    )

    # manual_trades.broker_connection_id → CASCADE on broker delete
    op.drop_constraint(
        "manual_trades_broker_connection_id_fkey", "manual_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "manual_trades_broker_connection_id_fkey",
        "manual_trades", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "strategies_broker_connection_id_fkey", "strategies", type_="foreignkey"
    )
    op.create_foreign_key(
        "strategies_broker_connection_id_fkey",
        "strategies", "broker_connections",
        ["broker_connection_id"], ["id"],
    )

    op.drop_constraint(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments", "broker_connections",
        ["broker_connection_id"], ["id"],
    )

    op.drop_constraint(
        "manual_trades_broker_connection_id_fkey", "manual_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "manual_trades_broker_connection_id_fkey",
        "manual_trades", "broker_connections",
        ["broker_connection_id"], ["id"],
    )
