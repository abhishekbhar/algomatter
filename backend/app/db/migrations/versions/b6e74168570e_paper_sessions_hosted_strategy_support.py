"""paper_sessions_hosted_strategy_support

Revision ID: b6e74168570e
Revises: 5b35c717713d
Create Date: 2026-03-28 11:04:17.731692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e74168570e'
down_revision: Union[str, None] = '5b35c717713d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_trading_sessions",
        sa.Column("strategy_code_id", sa.Uuid(), sa.ForeignKey("strategy_codes.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paper_trading_sessions", "strategy_code_id")
