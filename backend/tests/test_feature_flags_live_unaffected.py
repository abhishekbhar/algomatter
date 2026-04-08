"""Regression guard: when BOTH paper trading and backtesting are disabled,
the live deployment creation path must remain functional.
"""

import pytest

from app.config import settings
from tests.conftest import create_authenticated_user

STRATEGY_CODE = "class Strategy:\n    def on_candle(self, candle): pass"


async def _create_strategy(client, headers):
    resp = await client.post(
        "/api/v1/hosted-strategies",
        json={"name": "live-regression", "code": STRATEGY_CODE},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


@pytest.mark.asyncio
async def test_live_deployment_creation_reaches_broker_check_when_flags_off(
    client, monkeypatch
):
    """When both feature flags are off, live deployment creation must NOT be
    blocked by the feature-flag guards. It should instead reach the existing
    `broker_connection_id required for live mode` 400 (since we didn't supply
    one), proving the live path is unaffected by the flags.
    """
    tokens = await create_authenticated_user(client, email="lr1@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    monkeypatch.setattr(settings, "enable_paper_trading", False)
    monkeypatch.setattr(settings, "enable_backtesting", False)

    resp = await client.post(
        f"/api/v1/hosted-strategies/{strategy_id}/deployments",
        json={
            "mode": "live",
            "symbol": "NIFTY",
            "exchange": "NSE",
            "interval": "1d",
            # Intentionally no broker_connection_id
        },
        headers=headers,
    )

    # Must NOT be 403 (that would mean a flag is over-gating live mode).
    # Expect 400 from the existing "broker_connection_id required" check.
    assert resp.status_code != 403, (
        f"live deployment got 403 — feature flags are over-gating "
        f"the live path: {resp.json()}"
    )
    assert resp.status_code == 400
    assert "broker_connection_id" in resp.json()["detail"]
