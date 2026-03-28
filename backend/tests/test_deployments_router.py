import pytest

from tests.conftest import create_authenticated_user

STRATEGY_CODE = "class Strategy:\\n    def on_candle(self, candle): pass"


async def _create_strategy(client, headers: dict) -> str:
    """Helper: create a hosted strategy and return its id."""
    resp = await client.post(
        "/api/v1/hosted-strategies",
        json={"name": "Test SMA", "code": STRATEGY_CODE},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _create_deployment(client, headers: dict, strategy_id: str, **overrides) -> dict:
    """Helper: create a deployment with defaults."""
    payload = {
        "mode": "backtest",
        "symbol": "NIFTY",
        "exchange": "NSE",
        "interval": "1d",
        **overrides,
    }
    resp = await client.post(
        f"/api/v1/hosted-strategies/{strategy_id}/deployments",
        json=payload,
        headers=headers,
    )
    return resp


# ---------------------------------------------------------------------------
# 1. Create backtest deployment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_backtest_deployment(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    resp = await _create_deployment(client, headers, strategy_id, mode="backtest")
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode"] == "backtest"
    assert data["status"] == "pending"
    assert data["symbol"] == "NIFTY"
    assert data["exchange"] == "NSE"
    assert data["interval"] == "1d"
    assert data["strategy_code_id"] == strategy_id


# ---------------------------------------------------------------------------
# 2. Create paper deployment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_paper_deployment(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    resp = await _create_deployment(client, headers, strategy_id, mode="paper")
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode"] == "paper"
    assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# 3. Get deployment detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_deployment_detail(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id)
    deployment_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/deployments/{deployment_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == deployment_id


# ---------------------------------------------------------------------------
# 4. List deployments for strategy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_strategy_deployments(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    await _create_deployment(client, headers, strategy_id, mode="backtest")
    await _create_deployment(client, headers, strategy_id, mode="paper")

    resp = await client.get(
        f"/api/v1/hosted-strategies/{strategy_id}/deployments",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# 5. Pause a running deployment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_running_deployment(client, db_session):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id, mode="paper")
    deployment_id = create_resp.json()["id"]

    # Manually set status to "running" via DB so we can test pause
    from sqlalchemy import update, text as sa_text
    from app.db.models import StrategyDeployment
    import uuid

    await db_session.execute(
        update(StrategyDeployment)
        .where(StrategyDeployment.id == uuid.UUID(deployment_id))
        .values(status="running")
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/deployments/{deployment_id}/pause", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


# ---------------------------------------------------------------------------
# 6. Stop a deployment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_deployment(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id)
    deployment_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/deployments/{deployment_id}/stop", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


# ---------------------------------------------------------------------------
# 7. Stop all deployments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_all_deployments(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    await _create_deployment(client, headers, strategy_id, mode="backtest")
    await _create_deployment(client, headers, strategy_id, mode="paper")

    resp = await client.post("/api/v1/deployments/stop-all", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(d["status"] == "stopped" for d in data)


# ---------------------------------------------------------------------------
# 8. Promote completed backtest -> paper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promote_backtest_to_paper(client, db_session):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id, mode="backtest")
    deployment_id = create_resp.json()["id"]

    # Mark backtest as completed
    from sqlalchemy import update
    from app.db.models import StrategyDeployment
    import uuid

    await db_session.execute(
        update(StrategyDeployment)
        .where(StrategyDeployment.id == uuid.UUID(deployment_id))
        .values(status="completed")
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/deployments/{deployment_id}/promote",
        json={},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode"] == "paper"
    assert data["status"] == "pending"
    assert data["promoted_from_id"] == deployment_id


# ---------------------------------------------------------------------------
# 9. Promote paper -> live requires min ticks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promote_paper_to_live_requires_ticks(client, db_session):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id, mode="paper")
    deployment_id = create_resp.json()["id"]

    # Mark paper as running
    from sqlalchemy import update
    from app.db.models import StrategyDeployment
    import uuid

    await db_session.execute(
        update(StrategyDeployment)
        .where(StrategyDeployment.id == uuid.UUID(deployment_id))
        .values(status="running")
    )
    await db_session.commit()

    # Attempt promotion without enough ticks
    resp = await client.post(
        f"/api/v1/deployments/{deployment_id}/promote",
        json={"broker_connection_id": "00000000-0000-0000-0000-000000000001"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "ticks" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 10. Get deployment logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_deployment_logs(client, db_session):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strategy_id = await _create_strategy(client, headers)

    create_resp = await _create_deployment(client, headers, strategy_id)
    deployment_id = create_resp.json()["id"]

    # Insert some logs directly
    from app.db.models import DeploymentLog
    import uuid

    tenant_id = uuid.UUID(tokens["access_token"].split(".")[1][:36]) if False else None
    # We need the tenant_id from the user - extract from get deployment
    dep_detail = await client.get(
        f"/api/v1/deployments/{deployment_id}", headers=headers
    )
    # Get tenant_id from the token by decoding it
    import jwt
    from app.config import settings

    payload = jwt.decode(
        tokens["access_token"], settings.jwt_secret, algorithms=["HS256"]
    )
    tenant_id = uuid.UUID(payload["user_id"])

    for i in range(3):
        log = DeploymentLog(
            tenant_id=tenant_id,
            deployment_id=uuid.UUID(deployment_id),
            level="info",
            message=f"Log message {i}",
        )
        db_session.add(log)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/deployments/{deployment_id}/logs", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["logs"]) == 3
    assert data["offset"] == 0
    assert data["limit"] == 50
