import re
import uuid

from sqlalchemy import column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Strategy


def generate_slug(name: str) -> str:
    """Convert a strategy name to a URL-safe slug.

    'NIFTY Momentum' → 'nifty-momentum'
    'BankNifty Short!' → 'banknifty-short'
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


async def ensure_unique_slug(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    base_slug: str,
) -> str:
    """Return base_slug if unique within tenant, else base_slug-2, -3, …"""
    slug_col = column("slug")
    result = await session.execute(
        select(slug_col)
        .select_from(Strategy.__table__)
        .where(
            Strategy.__table__.c.tenant_id == tenant_id,
            slug_col.like(f"{base_slug}%"),
        )
    )
    existing = set(result.scalars().all())

    if base_slug not in existing:
        return base_slug

    n = 2
    while True:
        candidate = f"{base_slug}-{n}"
        if candidate not in existing:
            return candidate
        n += 1
