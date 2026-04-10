"""strategy_slug

Revision ID: b2c3d4e5f6a7
Revises: e5f6a7b8c9d0
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable column
    op.add_column("strategies", sa.Column("slug", sa.String(255), nullable=True))

    # 2. Backfill: generate slug from name, resolve collisions with window function
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                lower(trim(both '-' from regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))) AS base_slug,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id,
                    lower(trim(both '-' from regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g')))
                    ORDER BY created_at
                ) AS rn
            FROM strategies
        )
        UPDATE strategies s
        SET slug = CASE
            WHEN r.rn = 1 THEN r.base_slug
            ELSE r.base_slug || '-' || r.rn::text
        END
        FROM ranked r
        WHERE s.id = r.id
    """)

    # 3. Make NOT NULL and add unique constraint
    op.alter_column("strategies", "slug", nullable=False)
    op.create_unique_constraint(
        "uq_strategies_tenant_slug", "strategies", ["tenant_id", "slug"]
    )
    op.create_index("ix_strategies_slug", "strategies", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_strategies_slug", table_name="strategies")
    op.drop_constraint("uq_strategies_tenant_slug", "strategies", type_="unique")
    op.drop_column("strategies", "slug")
