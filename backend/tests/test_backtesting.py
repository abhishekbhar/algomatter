"""Tests for the backtesting engine and API."""

from decimal import Decimal

import pytest


# ---------------------------------------------------------------------------
# Test 1: Engine unit test (pure async, no DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backtest_engine_processes_signals():
    from app.backtesting.engine import run_backtest

    signals = [
        {
            "timestamp": "2025-01-02T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2500,
        },
        {
            "timestamp": "2025-01-03T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "SELL",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2600,
        },
    ]
    result = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    assert result["status"] == "completed"
    assert len(result["trade_log"]) == 2
    assert result["metrics"]["total_return"] > 0
    assert len(result["equity_curve"]) >= 2


@pytest.mark.asyncio
async def test_backtest_engine_with_slippage_and_commission():
    from app.backtesting.engine import run_backtest

    signals = [
        {
            "timestamp": "2025-01-02T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2500,
        },
        {
            "timestamp": "2025-01-03T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "SELL",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2600,
        },
    ]
    result_no_costs = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    result_with_costs = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0.1"),
        commission_pct=Decimal("0.1"),
    )
    # With costs, total return should be lower
    assert (
        result_with_costs["metrics"]["total_return"]
        < result_no_costs["metrics"]["total_return"]
    )


@pytest.mark.asyncio
async def test_backtest_engine_empty_signals():
    from app.backtesting.engine import run_backtest

    result = await run_backtest(
        signals=[],
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    assert result["status"] == "completed"
    assert len(result["trade_log"]) == 0
    assert result["metrics"]["total_trades"] == 0


@pytest.mark.asyncio
async def test_backtest_engine_signals_sorted_by_timestamp():
    """Signals provided out of order should still be processed chronologically."""
    from app.backtesting.engine import run_backtest

    signals = [
        {
            "timestamp": "2025-01-03T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "SELL",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2600,
        },
        {
            "timestamp": "2025-01-02T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2500,
        },
    ]
    result = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    assert result["status"] == "completed"
    # BUY should come first after sorting
    assert result["trade_log"][0]["action"] == "BUY"
    assert result["trade_log"][1]["action"] == "SELL"


@pytest.mark.asyncio
async def test_backtest_engine_trade_log_fields():
    """Each trade_log entry should have required fields."""
    from app.backtesting.engine import run_backtest

    signals = [
        {
            "timestamp": "2025-01-02T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2500,
        },
        {
            "timestamp": "2025-01-03T09:30:00",
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "SELL",
            "quantity": 10,
            "order_type": "MARKET",
            "price": 2600,
        },
    ]
    result = await run_backtest(
        signals=signals,
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0"),
        commission_pct=Decimal("0"),
    )
    for entry in result["trade_log"]:
        assert "timestamp" in entry
        assert "symbol" in entry
        assert "action" in entry
        assert "quantity" in entry
        assert "fill_price" in entry
        assert "status" in entry
        assert "pnl" in entry


# ---------------------------------------------------------------------------
# Test 2: API integration test (needs DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backtest_api_creates_and_returns(client):
    from tests.conftest import create_authenticated_user

    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "backtest-strat",
            "mode": "backtest",
            "mapping_template": {
                "symbol": "$.symbol",
                "exchange": "NSE",
                "action": "$.action",
                "quantity": "$.quantity",
                "order_type": "MARKET",
                "product_type": "INTRADAY",
            },
            "rules": {},
        },
        headers=headers,
    )
    strategy_id = strat.json()["id"]

    resp = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": strategy_id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "capital": 1000000,
            "slippage_pct": 0,
            "commission_pct": 0,
            "signals_csv": (
                "timestamp,symbol,action,quantity,order_type,price\n"
                "2025-01-02T09:30:00,RELIANCE,BUY,10,MARKET,2500\n"
                "2025-01-03T09:30:00,RELIANCE,SELL,10,MARKET,2600"
            ),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    backtest_id = resp.json()["id"]

    result = await client.get(
        f"/api/v1/backtests/{backtest_id}", headers=headers
    )
    assert result.json()["status"] == "completed"
    assert result.json()["metrics"]["total_return"] > 0


@pytest.mark.asyncio
async def test_backtest_api_list(client):
    from tests.conftest import create_authenticated_user

    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.get("/api/v1/backtests", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_backtest_api_delete(client):
    from tests.conftest import create_authenticated_user

    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    strat = await client.post(
        "/api/v1/strategies",
        json={
            "name": "backtest-del",
            "mode": "backtest",
            "mapping_template": {},
            "rules": {},
        },
        headers=headers,
    )
    strategy_id = strat.json()["id"]

    resp = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": strategy_id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "capital": 1000000,
            "slippage_pct": 0,
            "commission_pct": 0,
            "signals_csv": (
                "timestamp,symbol,action,quantity,order_type,price\n"
                "2025-01-02T09:30:00,RELIANCE,BUY,10,MARKET,2500\n"
                "2025-01-03T09:30:00,RELIANCE,SELL,10,MARKET,2600"
            ),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    backtest_id = resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/backtests/{backtest_id}", headers=headers
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/v1/backtests/{backtest_id}", headers=headers
    )
    assert get_resp.status_code == 404
