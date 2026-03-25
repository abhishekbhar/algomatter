import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.db.models  # noqa: F401 - ensure models are registered
from app.config import settings
from app.db.base import Base
from app.main import app

# Single test engine shared across tests (same event loop via session scope)
_test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)


def _patch_session_mod():
    import app.db.session as session_mod

    session_mod.engine = _test_engine
    session_mod.async_session_factory = _test_session_factory


# Patch immediately on import so the app uses the test engine
_patch_session_mod()


@pytest_asyncio.fixture
async def db_session():
    """Create tables, yield session, drop tables."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _test_session_factory() as session:
        yield session
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def create_authenticated_user(
    client: AsyncClient, email: str = "test@example.com"
) -> dict:
    """Helper -- not a fixture. Call from tests as: tokens = await create_authenticated_user(client)"""
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass123"},
    )
    return resp.json()
