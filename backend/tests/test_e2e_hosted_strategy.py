import uuid

import pytest
from sqlalchemy import update

from app.db.models import StrategyDeployment
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
class TestHostedStrategyLifecycle:
    """End-to-end test covering the full hosted strategy lifecycle."""

    async def test_full_lifecycle(self, client, db_session):
        # Auth
        tokens = await create_authenticated_user(client)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 1. Create hosted strategy
        sma_code = '''class Strategy(AlgoMatterStrategy):
    def on_init(self):
        self.state.setdefault("prices", [])

    def on_candle(self, candle):
        self.state["prices"].append(candle.close)
        if len(self.state["prices"]) >= 20:
            sma = sum(self.state["prices"][-20:]) / 20
            if candle.close > sma:
                self.buy(quantity=1)
            elif candle.close < sma and self.position:
                self.sell(quantity=1)
        self.log(f"Close: {candle.close}")
'''
        resp = await client.post("/api/v1/hosted-strategies", json={
            "name": "SMA Crossover E2E",
            "code": sma_code,
        }, headers=headers)
        assert resp.status_code == 201, resp.text
        strategy = resp.json()
        strategy_id = strategy["id"]
        assert strategy["name"] == "SMA Crossover E2E"
        assert strategy["version"] == 1

        # 2. Verify strategy appears in list
        resp = await client.get("/api/v1/hosted-strategies", headers=headers)
        assert resp.status_code == 200
        strategies = resp.json()
        assert any(s["id"] == strategy_id for s in strategies)

        # 3. Update strategy code (bump version)
        updated_code = sma_code + "\n    # Updated\n"
        resp = await client.put(f"/api/v1/hosted-strategies/{strategy_id}", json={
            "code": updated_code,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

        # 4. List versions (should have 2: initial + updated)
        resp = await client.get(
            f"/api/v1/hosted-strategies/{strategy_id}/versions", headers=headers
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == 2

        # 5. Create backtest deployment
        resp = await client.post(
            f"/api/v1/hosted-strategies/{strategy_id}/deployments",
            json={
                "mode": "backtest",
                "symbol": "BTCUSDT",
                "exchange": "BINANCE",
                "interval": "1h",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        backtest = resp.json()
        backtest_id = backtest["id"]
        assert backtest["mode"] == "backtest"
        assert backtest["status"] == "pending"

        # 6. Verify deployment detail
        resp = await client.get(
            f"/api/v1/deployments/{backtest_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "BTCUSDT"

        # 7. Create paper deployment
        resp = await client.post(
            f"/api/v1/hosted-strategies/{strategy_id}/deployments",
            json={
                "mode": "paper",
                "symbol": "ETHUSDT",
                "exchange": "BINANCE",
                "interval": "5m",
                "cron_expression": "*/5 * * * *",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        paper = resp.json()
        paper_id = paper["id"]
        assert paper["mode"] == "paper"

        # 8. List deployments for strategy (should have 2)
        resp = await client.get(
            f"/api/v1/hosted-strategies/{strategy_id}/deployments",
            headers=headers,
        )
        assert resp.status_code == 200
        deployments = resp.json()
        assert len(deployments) == 2

        # 9. Set paper to running (via direct DB update), then pause it
        await db_session.execute(
            update(StrategyDeployment)
            .where(StrategyDeployment.id == uuid.UUID(paper_id))
            .values(status="running")
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/deployments/{paper_id}/pause", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

        # 10. Resume then stop
        resp = await client.post(
            f"/api/v1/deployments/{paper_id}/resume", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        resp = await client.post(
            f"/api/v1/deployments/{paper_id}/stop", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
        assert resp.json()["stopped_at"] is not None

        # 11. Set backtest to completed, then promote to paper
        await db_session.execute(
            update(StrategyDeployment)
            .where(StrategyDeployment.id == uuid.UUID(backtest_id))
            .values(status="completed")
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/deployments/{backtest_id}/promote",
            json={},
            headers=headers,
        )
        assert resp.status_code == 201
        promoted = resp.json()
        promoted_id = promoted["id"]
        assert promoted["mode"] == "paper"
        assert promoted["promoted_from_id"] == backtest_id
        assert promoted["symbol"] == "BTCUSDT"  # inherits from parent

        # 12. Get deployment logs (should be empty but endpoint works)
        resp = await client.get(
            f"/api/v1/deployments/{backtest_id}/logs", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        # 13. Get deployment results (empty list)
        resp = await client.get(
            f"/api/v1/deployments/{backtest_id}/results", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

        # 14. Get strategy templates
        resp = await client.get("/api/v1/strategy-templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 4

        # 15. Stop all active deployments
        # Set the promoted deployment to running first so stop-all has something to stop
        await db_session.execute(
            update(StrategyDeployment)
            .where(StrategyDeployment.id == uuid.UUID(promoted_id))
            .values(status="running")
        )
        await db_session.commit()

        resp = await client.post(
            "/api/v1/deployments/stop-all", headers=headers
        )
        assert resp.status_code == 200
        stopped_list = resp.json()
        assert len(stopped_list) >= 1
        assert all(d["status"] == "stopped" for d in stopped_list)

        # 16. List all user deployments with status filter
        resp = await client.get(
            "/api/v1/deployments?status=stopped", headers=headers
        )
        assert resp.status_code == 200
        stopped = resp.json()
        assert len(stopped) >= 2  # paper + promoted were stopped

        # Expire db_session state so it doesn't conflict with cascading deletes
        # performed by the API in its own session.
        db_session.expunge_all()

        # 17. Delete strategy
        resp = await client.delete(
            f"/api/v1/hosted-strategies/{strategy_id}", headers=headers
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(
            f"/api/v1/hosted-strategies/{strategy_id}", headers=headers
        )
        assert resp.status_code == 404
