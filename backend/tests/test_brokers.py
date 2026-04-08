# tests/test_brokers.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from app.brokers.base import OrderRequest, OrderResponse, Position, AccountBalance
from app.brokers.exchange1 import Exchange1Broker
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


def test_order_request_position_side_defaults_to_none():
    order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES",
    )
    assert order.position_side is None


def test_order_request_position_side_accepts_long_and_short():
    long_order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES", position_side="long",
    )
    short_order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="SELL",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="short",
    )
    assert long_order.position_side == "long"
    assert short_order.position_side == "short"


# ---------------------------------------------------------------------------
# Exchange1 futures path tests (mocked, no live API calls)
# ---------------------------------------------------------------------------

def _make_exchange1() -> Exchange1Broker:
    """Return an Exchange1Broker with signing infrastructure mocked out."""
    broker = Exchange1Broker()
    broker._api_key = "test-key"
    broker._recv_window = "5000"
    # Mock _post and _get so no real HTTP calls are made
    broker._post = AsyncMock()
    broker._get = AsyncMock()
    return broker


def test_futures_symbol_conversion():
    assert Exchange1Broker._futures_symbol("BTCUSDT") == "btc"
    assert Exchange1Broker._futures_symbol("ETHUSDT") == "eth"
    assert Exchange1Broker._futures_symbol("BTC") == "btc"
    assert Exchange1Broker._futures_symbol("SOLUSDT") == "sol"
    assert Exchange1Broker._futures_symbol("btcusdt") == "btc"


@pytest.mark.asyncio
async def test_exchange1_futures_buy_builds_correct_body():
    broker = _make_exchange1()
    broker._post.return_value = {"data": "98765"}

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("2"),
        order_type="LIMIT",
        price=Decimal("66000"),
        product_type="FUTURES",
        # position_model omitted → defaults to "cross"
    )
    resp = await broker.place_order(order)

    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/create",
        body={
            "symbol": "btc",
            "positionType": "limit",
            "positionSide": "long",
            "quantity": "2",
            "quantityUnit": "cont",
            "positionModel": "cross",
            "leverage": "10",
            "price": "66000",
        },
        signed=True,
    )
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:98765"


@pytest.mark.asyncio
async def test_exchange1_futures_leverage_and_cross_margin():
    broker = _make_exchange1()
    broker._post.return_value = {"data": "55555"}

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("1"),
        order_type="MARKET",
        price=Decimal("0"),
        product_type="FUTURES",
        leverage=20,
        position_model="cross",
    )
    await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["leverage"] == "20"
    assert body["positionModel"] == "cross"


@pytest.mark.asyncio
async def test_exchange1_futures_isolated_is_fix():
    broker = _make_exchange1()
    broker._post.return_value = {"data": "66666"}

    order = OrderRequest(
        symbol="ETHUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("1"),
        order_type="MARKET",
        price=Decimal("0"),
        product_type="FUTURES",
        position_model="isolated",
    )
    await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionModel"] == "fix"


@pytest.mark.asyncio
async def test_exchange1_futures_tp_sl_both_rejected():
    """TP or SL on futures → rejected before any API call (Exchange1 sign error)."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("1"),
        order_type="LIMIT",
        price=Decimal("65000"),
        product_type="FUTURES",
        leverage=10,
        take_profit=Decimal("70000"),
        stop_loss=Decimal("62000"),
    )
    resp = await broker.place_order(order)

    # take_profit is checked first — no API call made
    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "take_profit" in resp.message.lower()


@pytest.mark.asyncio
async def test_exchange1_futures_sell_closes_position():
    """SELL on futures (default long side) → close via /openapi/v1/futures/order/close."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "11111"}

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="SELL",
        quantity=Decimal("1"),
        order_type="MARKET",
        price=Decimal("0"),
        product_type="FUTURES",
    )
    resp = await broker.place_order(order)

    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/close",
        body={"symbol": "btc", "positionType": "market", "closeType": "all"},
        signed=True,
    )
    assert resp.order_id == "futures:market:btc:11111"


@pytest.mark.asyncio
async def test_exchange1_futures_sell_limit_includes_price():
    broker = _make_exchange1()
    broker._post.return_value = {"data": "22222"}

    order = OrderRequest(
        symbol="ETHUSDT",
        exchange="exchange1",
        action="SELL",
        quantity=Decimal("1"),
        order_type="LIMIT",
        price=Decimal("3200"),
        product_type="FUTURES",
    )
    resp = await broker.place_order(order)

    call_body = broker._post.call_args.kwargs["body"]
    assert broker._post.call_args.args[0] == "/openapi/v1/futures/order/close"
    assert call_body["symbol"] == "eth"
    assert call_body["closeType"] == "all"
    assert call_body["price"] == "3200"


@pytest.mark.asyncio
async def test_exchange1_futures_cancel_routes_correctly():
    broker = _make_exchange1()
    broker._post.return_value = {}

    await broker.cancel_order("futures:limit:btc:42")
    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/cancel",
        body={"id": "42", "symbol": "btc", "positionType": "limit"},
        signed=True,
    )


@pytest.mark.asyncio
async def test_exchange1_spot_cancel_routes_correctly():
    broker = _make_exchange1()
    broker._post.return_value = {}

    await broker.cancel_order("spot-order-99")
    broker._post.assert_called_once_with(
        "/openapi/v1/spot/order/cancel",
        body={"id": "spot-order-99"},
        signed=True,
    )


@pytest.mark.asyncio
async def test_exchange1_futures_order_status_filled_when_absent():
    """Order not in current orders list → treat as filled."""
    broker = _make_exchange1()
    # Exchange1 returns rows under "data.rows", not "data.list"
    broker._get.return_value = {"data": {"rows": []}}

    status = await broker.get_order_status("futures:market:btc:999")

    assert status.status == "filled"
    assert status.order_id == "futures:market:btc:999"


@pytest.mark.asyncio
async def test_exchange1_buy_long_routes_to_create_with_long_side():
    """BUY + position_side=None (default) → /futures/order/create with positionSide=long."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "100001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES", leverage=10, position_model="cross",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/create"
    body = call_args.kwargs["body"]
    assert body["positionSide"] == "long"
    assert body["positionModel"] == "cross"
    assert body["leverage"] == "10"
    assert body["price"] == "60000"
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:100001"


@pytest.mark.asyncio
async def test_exchange1_buy_explicit_long_side():
    """BUY + position_side='long' → same as default."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "100002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="long",
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionSide"] == "long"
    assert resp.status == "filled"
    assert resp.order_id == "futures:market:btc:100002"


@pytest.mark.asyncio
async def test_exchange1_open_short_routes_to_create_with_short_side():
    """SELL + position_side='short' → /futures/order/create with positionSide=short."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "200001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="SELL",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("80000"),
        product_type="FUTURES", leverage=5, position_model="cross",
        position_side="short",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/create"
    body = call_args.kwargs["body"]
    assert body["positionSide"] == "short"
    assert body["positionModel"] == "cross"
    assert body["price"] == "80000"
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:200001"


@pytest.mark.asyncio
async def test_exchange1_close_short_routes_to_close():
    """BUY + position_side='short' → /futures/order/close (close the short)."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "200002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="short",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/close"
    body = call_args.kwargs["body"]
    assert body["closeType"] == "all"
    assert resp.status == "filled"
    assert resp.order_id == "futures:market:btc:200002"


@pytest.mark.asyncio
async def test_exchange1_futures_take_profit_rejected():
    """take_profit on a futures order → rejected before any API call."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", take_profit=Decimal("70000"),
    )
    resp = await broker.place_order(order)

    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "take_profit" in resp.message.lower()


@pytest.mark.asyncio
async def test_exchange1_futures_stop_loss_rejected():
    """stop_loss on a futures order → rejected before any API call."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", stop_loss=Decimal("62000"),
    )
    resp = await broker.place_order(order)

    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "stop_loss" in resp.message.lower()


@pytest.mark.asyncio
async def test_exchange1_futures_sl_order_type_sends_price():
    """order_type='SL' maps to positionType='limit' and must include price."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="SL", price=Decimal("58000"),
        product_type="FUTURES", leverage=10, position_model="cross",
        trigger_price=Decimal("59000"),
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionType"] == "limit"
    assert body["price"] == "58000"
    assert resp.status == "open"


@pytest.mark.asyncio
async def test_exchange1_futures_sl_m_order_type_sends_price():
    """order_type='SL-M' maps to positionType='limit' and must include price."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="SL-M", price=Decimal("57000"),
        product_type="FUTURES", leverage=10, position_model="cross",
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionType"] == "limit"
    assert body["price"] == "57000"
    assert resp.status == "open"


@pytest.mark.asyncio
async def test_exchange1_futures_partial_close_uses_trigger_price_as_position_id():
    """trigger_price on a close order → closeType=<position_id>, closeNum set."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300003"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="SELL",
        quantity=Decimal("2"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES",
        trigger_price=Decimal("700340577325424640"),  # position ID from Exchange1
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["closeType"] == "700340577325424640"
    assert body["closeNum"] == "2"
    assert resp.status == "filled"
