from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token
from app.db.session import activate_rls, async_session_factory

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_access_token(credentials.credentials)
        return payload  # {"user_id": "...", "email": "..."}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


async def get_tenant_session(
    current_user: dict = Depends(get_current_user),
) -> AsyncSession:
    session = async_session_factory()
    activate_rls(session, current_user["user_id"])
    try:
        yield session
    finally:
        await session.close()


async def get_session() -> AsyncSession:
    """Non-RLS session for auth endpoints (signup/login)."""
    async with async_session_factory() as session:
        yield session
