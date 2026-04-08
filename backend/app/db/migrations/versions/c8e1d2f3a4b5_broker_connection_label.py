"""broker_connection_label

Revision ID: c8e1d2f3a4b5
Revises: b7d4e9f1a2c3
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e1d2f3a4b5'
down_revision: Union[str, None] = 'b7d4e9f1a2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column as nullable so backfill can run
    op.add_column(
        'broker_connections',
        sa.Column('label', sa.String(length=40), nullable=True),
    )

    # 2. Backfill every existing row with a unique placeholder:
    #    "<broker_type> #<first 8 chars of id>"
    op.execute(
        """
        UPDATE broker_connections
        SET label = broker_type || ' #' || substr(id::text, 1, 8)
        WHERE label IS NULL
        """
    )

    # 3. Flip to NOT NULL now that every row has a value
    op.alter_column('broker_connections', 'label', nullable=False)

    # 4. Composite unique index: a label is unique within a tenant
    op.create_index(
        'ix_broker_connections_tenant_label',
        'broker_connections',
        ['tenant_id', 'label'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_broker_connections_tenant_label', table_name='broker_connections')
    op.drop_column('broker_connections', 'label')
