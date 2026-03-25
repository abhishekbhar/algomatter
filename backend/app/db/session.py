from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_size=20)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


def activate_rls(session: AsyncSession, tenant_id: str):
    """Register an after_begin hook that sets the RLS tenant context.

    Note: SET LOCAL does not support bind parameters in asyncpg ($1 syntax).
    We validate the tenant_id as a UUID to prevent SQL injection, then use
    a quoted string literal.
    """
    import uuid

    # Validate tenant_id is a valid UUID — prevents SQL injection
    validated = str(uuid.UUID(str(tenant_id)))

    @event.listens_for(session.sync_session, "after_begin")
    def set_tenant(session, transaction, connection):
        connection.execute(
            text(f"SET LOCAL app.current_tenant_id = '{validated}'")
        )
