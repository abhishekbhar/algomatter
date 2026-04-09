"""webhook_signal_received_at_index

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-04-09 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_webhook_signals_tenant_received",
        "webhook_signals",
        ["tenant_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_signals_tenant_received", table_name="webhook_signals")
