# tests/test_brokers.py
import pytest
from decimal import Decimal
from app.brokers.base import OrderRequest, OrderResponse, Position, AccountBalance
from app.brokers.simulated import SimulatedBroker


@pytest.mark.asyncio
async def test_simulated_initial_balance():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    balance = await broker.get_balance()
    assert balance.available == Decimal("1000000")


@pytest.mark.asyncio
async def test_simulated_place_buy_order():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    order = OrderRequest(
        symbol="RELIANCE",
        exchange="NSE",
        action="BUY",
        quantity=Decimal("10"),
        order_type="MARKET",
        price=Decimal("2500"),
        product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.status == "filled"
    assert resp.fill_price == Decimal("2500")  # no slippage configured
    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "RELIANCE"
    assert positions[0].quantity == Decimal("10")


@pytest.mark.asyncio
async def test_simulated_slippage():
    broker = SimulatedBroker(
        initial_capital=Decimal("1000000"),
        slippage_pct=Decimal("0.1"),  # 0.1%
    )
    order = OrderRequest(
        symbol="TCS",
        exchange="NSE",
        action="BUY",
        quantity=Decimal("5"),
        order_type="MARKET",
        price=Decimal("1000"),
        product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.fill_price == Decimal("1001")  # 1000 + 0.1%


@pytest.mark.asyncio
async def test_simulated_sell_reduces_position():
    broker = SimulatedBroker(initial_capital=Decimal("1000000"))
    await broker.place_order(
        OrderRequest(
            symbol="INFY",
            exchange="NSE",
            action="BUY",
            quantity=Decimal("20"),
            order_type="MARKET",
            price=Decimal("1500"),
            product_type="INTRADAY",
        )
    )
    await broker.place_order(
        OrderRequest(
            symbol="INFY",
            exchange="NSE",
            action="SELL",
            quantity=Decimal("20"),
            order_type="MARKET",
            price=Decimal("1600"),
            product_type="INTRADAY",
        )
    )
    positions = await broker.get_positions()
    open_positions = [p for p in positions if p.closed_at is None]
    assert len(open_positions) == 0


@pytest.mark.asyncio
async def test_simulated_insufficient_balance():
    broker = SimulatedBroker(initial_capital=Decimal("100"))
    order = OrderRequest(
        symbol="RELIANCE",
        exchange="NSE",
        action="BUY",
        quantity=Decimal("10"),
        order_type="MARKET",
        price=Decimal("2500"),
        product_type="INTRADAY",
    )
    resp = await broker.place_order(order)
    assert resp.status == "rejected"
