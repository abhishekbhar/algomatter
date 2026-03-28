"""Tests for BinanceTestnetBroker — signing, authentication, connection, and orders."""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx

from app.brokers.base import OrderRequest
from app.brokers.binance_testnet import BASE_URL, BinanceTestnetBroker


def _make_authenticated_broker() -> BinanceTestnetBroker:
    """Return a broker pre-configured with dummy credentials and an HTTP client."""
    broker = BinanceTestnetBroker()
    broker._api_key = "test-key"
    broker._secret = "test-secret"
    broker._client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
    broker._time_offset_ms = 0
    return broker


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


class TestSigning:
    """Unit tests for HMAC-SHA256 request signing."""

    def test_sign_produces_valid_hmac(self):
        broker = BinanceTestnetBroker()
        broker._secret = "my_secret_key"
        broker._time_offset_ms = 0

        with patch("app.brokers.binance_testnet.time.time", return_value=1700000000.0):
            signed = broker._sign({"symbol": "BTCUSDT", "side": "BUY"})

        # Manually compute expected signature
        query = "symbol=BTCUSDT&side=BUY&timestamp=1700000000000"
        expected_sig = hmac.new(
            b"my_secret_key", query.encode(), hashlib.sha256
        ).hexdigest()

        assert signed["signature"] == expected_sig
        assert signed["timestamp"] == 1700000000000
        assert signed["symbol"] == "BTCUSDT"

    def test_sign_applies_time_offset(self):
        broker = BinanceTestnetBroker()
        broker._secret = "secret"
        broker._time_offset_ms = 500  # server is 500 ms ahead

        with patch("app.brokers.binance_testnet.time.time", return_value=1700000000.0):
            signed = broker._sign({})

        assert signed["timestamp"] == 1700000000500


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class TestConnection:
    """Integration-style tests using mocked HTTP responses."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        # Mock /api/v3/time
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=httpx.Response(200, json={"serverTime": 1700000000000})
        )
        # Mock /api/v3/account
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json={"balances": []})
        )

        broker = BinanceTestnetBroker()
        with patch("app.brokers.binance_testnet.time.time", return_value=1700000000.0):
            result = await broker.authenticate(
                {"api_key": "test_key", "api_secret": "test_secret"}
            )

        assert result is True
        assert broker._api_key == "test_key"
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_bad_credentials(self):
        # Mock /api/v3/time
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=httpx.Response(200, json={"serverTime": 1700000000000})
        )
        # Mock /api/v3/account returning 401
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(
                401, json={"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}
            )
        )

        broker = BinanceTestnetBroker()
        with patch("app.brokers.binance_testnet.time.time", return_value=1700000000.0):
            result = await broker.authenticate(
                {"api_key": "bad_key", "api_secret": "bad_secret"}
            )

        assert result is False
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_verify_connection_success(self):
        respx.get(f"{BASE_URL}/api/v3/ping").mock(
            return_value=httpx.Response(200, json={})
        )

        broker = BinanceTestnetBroker()
        result = await broker.verify_connection()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_clock_offset_computed(self):
        server_time = 1700000005000  # server is 5 seconds ahead
        local_time = 1700000000.0  # local epoch seconds

        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=httpx.Response(200, json={"serverTime": server_time})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json={"balances": []})
        )

        broker = BinanceTestnetBroker()
        with patch("app.brokers.binance_testnet.time.time", return_value=local_time):
            await broker.authenticate(
                {"api_key": "key", "api_secret": "secret"}
            )

        assert broker._time_offset_ms == 5000
        await broker.close()

    @pytest.mark.asyncio
    async def test_close_clears_secrets(self):
        broker = BinanceTestnetBroker()
        broker._api_key = "some_key"
        broker._secret = "some_secret"
        broker._time_offset_ms = 1234
        broker._account_cache = (time.time(), {"balances": []})
        broker._client = httpx.AsyncClient()

        await broker.close()

        assert broker._api_key == ""
        assert broker._secret == ""
        assert broker._time_offset_ms == 0
        assert broker._account_cache is None
        assert broker._client is None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def _market_order(symbol: str = "BTCUSDT", action: str = "BUY", qty: str = "0.01") -> OrderRequest:
    """Convenience factory for a MARKET OrderRequest."""
    return OrderRequest(
        symbol=symbol,
        exchange="BINANCE_TESTNET",
        action=action,
        quantity=Decimal(qty),
        order_type="MARKET",
        price=Decimal("0"),
        product_type="DELIVERY",
    )


def _limit_order(
    symbol: str = "BTCUSDT",
    action: str = "BUY",
    qty: str = "0.01",
    price: str = "30000.00",
) -> OrderRequest:
    return OrderRequest(
        symbol=symbol,
        exchange="BINANCE_TESTNET",
        action=action,
        quantity=Decimal(qty),
        order_type="LIMIT",
        price=Decimal(price),
        product_type="DELIVERY",
    )


_FILLED_RESPONSE = {
    "orderId": 12345,
    "status": "FILLED",
    "executedQty": "0.01",
    "cummulativeQuoteQty": "300.00",
    "origQty": "0.01",
}

_NEW_RESPONSE = {
    "orderId": 67890,
    "status": "NEW",
    "executedQty": "0",
    "cummulativeQuoteQty": "0",
    "origQty": "0.01",
}

_PARTIALLY_FILLED_RESPONSE = {
    "orderId": 11111,
    "status": "PARTIALLY_FILLED",
    "executedQty": "0.005",
    "cummulativeQuoteQty": "150.00",
    "origQty": "0.01",
}


class TestOrders:
    """Tests for place_order, cancel_order, and get_order_status."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_market_order(self):
        route = respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_FILLED_RESPONSE)
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker._client.aclose()

        assert route.called
        assert resp.order_id == "12345"
        assert resp.status == "filled"
        assert resp.fill_price == Decimal("300.00") / Decimal("0.01")
        assert resp.fill_quantity == Decimal("0.01")

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_limit_order(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_NEW_RESPONSE)
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_limit_order())
        await broker._client.aclose()

        assert resp.order_id == "67890"
        assert resp.status == "open"
        assert resp.fill_price is None
        assert resp.fill_quantity is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_rejected(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(
                400, json={"code": -1013, "msg": "Filter failure: LOT_SIZE"}
            )
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker._client.aclose()

        assert resp.status == "rejected"
        assert resp.order_id == ""
        assert "400" in resp.message

    @respx.mock
    @pytest.mark.asyncio
    async def test_partially_filled_maps_to_open(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_PARTIALLY_FILLED_RESPONSE)
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker._client.aclose()

        assert resp.status == "open"
        assert resp.fill_price == Decimal("150.00") / Decimal("0.005")
        assert resp.fill_quantity == Decimal("0.005")

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_stores_symbol_in_map(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_FILLED_RESPONSE)
        )

        broker = _make_authenticated_broker()
        await broker.place_order(_market_order(symbol="ETHUSDT"))
        await broker._client.aclose()

        assert broker._order_symbols["12345"] == "ETHUSDT"

    @respx.mock
    @pytest.mark.asyncio
    async def test_cancel_order(self):
        # Place first so that _order_symbols is populated
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_FILLED_RESPONSE)
        )
        respx.delete(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json={"orderId": 12345, "status": "CANCELED"})
        )

        broker = _make_authenticated_broker()
        await broker.place_order(_market_order())
        result = await broker.cancel_order("12345")
        await broker._client.aclose()

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_order_unknown_id_raises(self):
        broker = _make_authenticated_broker()

        with pytest.raises(ValueError, match="Unknown order_id"):
            await broker.cancel_order("9999999")

        await broker._client.aclose()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_stop_loss_limit_order(self):
        sl_response = {
            "orderId": 22222,
            "status": "NEW",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "origQty": "0.01",
        }
        route = respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=sl_response)
        )

        order = OrderRequest(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="SELL",
            quantity=Decimal("0.01"),
            order_type="SL",
            price=Decimal("29000.00"),
            product_type="DELIVERY",
            trigger_price=Decimal("29500.00"),
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(order)
        await broker._client.aclose()

        assert resp.order_id == "22222"
        assert resp.status == "open"

        # Verify the request sent to Binance had the right params
        request = route.calls[0].request
        url_str = str(request.url)
        assert "type=STOP_LOSS_LIMIT" in url_str
        assert "stopPrice=29500.00" in url_str
        assert "price=29000.00" in url_str
        assert "timeInForce=GTC" in url_str

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_stop_loss_market_order(self):
        slm_response = {
            "orderId": 33333,
            "status": "NEW",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
            "origQty": "0.01",
        }
        route = respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=slm_response)
        )

        order = OrderRequest(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="SELL",
            quantity=Decimal("0.01"),
            order_type="SL-M",
            price=Decimal("0"),
            product_type="DELIVERY",
            trigger_price=Decimal("29500.00"),
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(order)
        await broker._client.aclose()

        assert resp.order_id == "33333"
        assert resp.status == "open"

        request = route.calls[0].request
        url_str = str(request.url)
        assert "type=STOP_LOSS" in url_str
        assert "STOP_LOSS_LIMIT" not in url_str
        assert "stopPrice=29500.00" in url_str

    @pytest.mark.asyncio
    async def test_get_order_status_unknown_id_raises(self):
        broker = _make_authenticated_broker()

        with pytest.raises(ValueError, match="Unknown order_id"):
            await broker.get_order_status("9999999")

        await broker._client.aclose()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status(self):
        # Place order to populate _order_symbols
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json=_FILLED_RESPONSE)
        )
        # Mock GET for order status query
        respx.get(f"{BASE_URL}/api/v3/order").mock(
            return_value=httpx.Response(200, json={
                "orderId": 12345,
                "status": "FILLED",
                "executedQty": "0.01",
                "cummulativeQuoteQty": "300.00",
                "origQty": "0.01",
            })
        )

        broker = _make_authenticated_broker()
        await broker.place_order(_market_order())
        status = await broker.get_order_status("12345")
        await broker._client.aclose()

        assert status.order_id == "12345"
        assert status.status == "filled"
        assert status.fill_price == Decimal("300.00") / Decimal("0.01")
        assert status.fill_quantity == Decimal("0.01")
        assert status.pending_quantity is None


# ---------------------------------------------------------------------------
# Portfolio / Balance
# ---------------------------------------------------------------------------

ACCOUNT_RESPONSE = {
    "balances": [
        {"asset": "BTC", "free": "0.5", "locked": "0.1"},
        {"asset": "ETH", "free": "10.0", "locked": "0.0"},
        {"asset": "USDT", "free": "5000.0", "locked": "1000.0"},
        {"asset": "USDC", "free": "2000.0", "locked": "0.0"},
        {"asset": "BNB", "free": "0.0", "locked": "0.0"},
    ]
}


class TestPortfolio:
    """Tests for get_balance, get_positions, get_holdings, and account caching."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_balance(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        balance = await broker.get_balance()
        await broker._client.aclose()

        assert balance.available == Decimal("7000.0")
        assert balance.used_margin == Decimal("1000.0")
        assert balance.total == Decimal("8000.0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_excludes_quote_assets(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()
        await broker._client.aclose()

        symbols = {p.symbol for p in positions}
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "USDT" not in symbols
        assert "USDC" not in symbols
        assert "BNB" not in symbols  # zero balance excluded

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_fields(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()
        await broker._client.aclose()

        btc = next(p for p in positions if p.symbol == "BTC")
        assert btc.quantity == Decimal("0.6")
        assert btc.exchange == "BINANCE_TESTNET"
        assert btc.action == "BUY"
        assert btc.entry_price == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_holdings(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        holdings = await broker.get_holdings()
        await broker._client.aclose()

        symbols = {h.symbol for h in holdings}
        assert symbols == {"BTC", "ETH"}

        btc = next(h for h in holdings if h.symbol == "BTC")
        assert btc.quantity == Decimal("0.6")
        assert btc.exchange == "BINANCE_TESTNET"
        assert btc.average_price == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_account_cache_prevents_duplicate_calls(self):
        route = respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=httpx.Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        await broker.get_balance()
        await broker.get_positions()
        await broker.get_holdings()
        await broker._client.aclose()

        assert route.call_count == 1
