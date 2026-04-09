"""add_position_side_to_manual_trades

Revision ID: e1f2a3b4c5d6
Revises: c8e1d2f3a4b5
Create Date: 2026-04-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "c8e1d2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "manual_trades",
        sa.Column("position_side", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manual_trades", "position_side")
