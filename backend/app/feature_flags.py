"""FastAPI dependency functions that guard write endpoints behind feature flags.

These are imported and used via `Depends(...)` on router endpoints, or called
inline inside handlers where the guard must be conditional on a request field
(e.g. `mode` in the deployment creation endpoint).
"""

from fastapi import HTTPException, status

from app.config import settings


def require_paper_trading_enabled() -> None:
    if not settings.enable_paper_trading:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Paper trading is disabled",
        )


def require_backtesting_enabled() -> None:
    if not settings.enable_backtesting:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Backtesting is disabled",
        )
