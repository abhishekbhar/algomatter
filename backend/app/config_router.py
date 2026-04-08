"""Public config endpoint exposing feature flags to the frontend.

Intentionally unauthenticated: the response contains only boolean feature
flags (no secrets), and the frontend needs to fetch it before the user is
logged in so the sidebar can be filtered correctly on first render.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("")
def get_public_config() -> dict:
    return {
        "featureFlags": {
            "paperTrading": settings.enable_paper_trading,
            "backtesting": settings.enable_backtesting,
        }
    }
