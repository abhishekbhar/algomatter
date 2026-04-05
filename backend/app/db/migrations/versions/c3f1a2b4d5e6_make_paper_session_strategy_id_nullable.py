"""make_paper_session_strategy_id_nullable

Revision ID: c3f1a2b4d5e6
Revises: b6e74168570e
Create Date: 2026-04-05 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1a2b4d5e6'
down_revision: Union[str, None] = '919540c9ed52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "paper_trading_sessions",
        "strategy_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "paper_trading_sessions",
        "strategy_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
