"""Tests for Exchange1Broker — RSA signing, authentication, orders, portfolio, and market data."""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from httpx import Response

from app.brokers.base import OrderRequest
from app.brokers.exchange1 import BASE_URL, BINANCE_URL, Exchange1Broker

# ---------------------------------------------------------------------------
# Shared test RSA key pair
# ---------------------------------------------------------------------------

_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PRIVATE_KEY_PEM = _TEST_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _make_authenticated_broker() -> Exchange1Broker:
    """Return a broker pre-configured with test RSA credentials and an HTTP client."""
    broker = Exchange1Broker()
    broker._api_key = "test-api-key"
    broker._private_key = _TEST_PRIVATE_KEY_PEM
    broker._private_key_obj = _TEST_PRIVATE_KEY
    broker._recv_window = "5000"
    broker._client = httpx.AsyncClient(timeout=10.0)
    return broker


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


class TestSigning:
    """Unit tests for RSA SHA256WithRSA request signing."""

    def test_build_signed_headers_returns_all_required_headers(self):
        broker = _make_authenticated_broker()

        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            headers = broker._build_signed_headers({"symbol": "btcusdt", "quantity": "0.001"})

        assert headers["X-SAASAPI-API-KEY"] == "test-api-key"
        assert headers["X-SAASAPI-TIMESTAMP"] == "1700000000000"
        assert headers["X-SAASAPI-RECV-WINDOW"] == "5000"
        assert "X-SAASAPI-SIGN" in headers
        assert headers["Content-Type"] == "application/json"

    def test_signature_is_valid_rsa_sha256(self):
        broker = _make_authenticated_broker()

        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            headers = broker._build_signed_headers({"symbol": "btcusdt", "quantity": "0.001"})

        # Reconstruct expected payload
        payload = "1700000000000test-api-key5000quantity=0.001&symbol=btcusdt"
        signature_bytes = base64.b64decode(headers["X-SAASAPI-SIGN"])

        # Verify the signature with the public key
        public_key = _TEST_PRIVATE_KEY.public_key()
        public_key.verify(
            signature_bytes,
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        # No exception = valid signature

    def test_sorted_params_ascii_order(self):
        broker = _make_authenticated_broker()

        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            headers = broker._build_signed_headers({"z_param": "last", "a_param": "first"})

        payload = "1700000000000test-api-key5000a_param=first&z_param=last"
        signature_bytes = base64.b64decode(headers["X-SAASAPI-SIGN"])
        public_key = _TEST_PRIVATE_KEY.public_key()
        public_key.verify(
            signature_bytes,
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_empty_values_excluded_from_params(self):
        broker = _make_authenticated_broker()

        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            headers = broker._build_signed_headers({"symbol": "btcusdt", "empty": "", "none_val": None})

        payload = "1700000000000test-api-key5000symbol=btcusdt"
        signature_bytes = base64.b64decode(headers["X-SAASAPI-SIGN"])
        public_key = _TEST_PRIVATE_KEY.public_key()
        public_key.verify(
            signature_bytes,
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_no_params_produces_valid_signature(self):
        broker = _make_authenticated_broker()

        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            headers = broker._build_signed_headers({})

        payload = "1700000000000test-api-key5000"
        signature_bytes = base64.b64decode(headers["X-SAASAPI-SIGN"])
        public_key = _TEST_PRIVATE_KEY.public_key()
        public_key.verify(
            signature_bytes,
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class TestConnection:
    """Tests for authenticate, verify_connection, and close."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.post(f"{BASE_URL}/openapi/v1/token").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success"})
        )

        broker = Exchange1Broker()
        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            result = await broker.authenticate(
                {"api_key": "test-key", "private_key": _TEST_PRIVATE_KEY_PEM}
            )

        assert result is True
        assert broker._api_key == "test-key"
        assert broker._private_key_obj is not None
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_bad_credentials(self):
        respx.post(f"{BASE_URL}/openapi/v1/token").mock(
            return_value=httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        )

        broker = Exchange1Broker()
        with patch("app.brokers.exchange1.time.time", return_value=1700000000.0):
            result = await broker.authenticate(
                {"api_key": "bad-key", "private_key": _TEST_PRIVATE_KEY_PEM}
            )

        assert result is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_verify_connection_success(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": []})
        )

        broker = _make_authenticated_broker()
        result = await broker.verify_connection()
        await broker.close()

        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_verify_connection_failure(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        )

        broker = _make_authenticated_broker()
        result = await broker.verify_connection()
        await broker.close()

        assert result is False

    @pytest.mark.asyncio
    async def test_close_clears_secrets(self):
        broker = _make_authenticated_broker()
        broker._binance_client = httpx.AsyncClient()
        broker._account_cache = (time.time(), [])

        await broker.close()

        assert broker._api_key == ""
        assert broker._private_key == ""
        assert broker._private_key_obj is None
        assert broker._client is None
        assert broker._binance_client is None
        assert broker._account_cache is None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def _market_order(symbol: str = "BTCUSDT", action: str = "BUY", qty: str = "0.001") -> OrderRequest:
    return OrderRequest(
        symbol=symbol, exchange="EXCHANGE1", action=action,
        quantity=Decimal(qty), order_type="MARKET", price=Decimal("0"), product_type="DELIVERY",
    )


def _limit_order(
    symbol: str = "BTCUSDT", action: str = "BUY", qty: str = "0.001", price: str = "66000.00",
) -> OrderRequest:
    return OrderRequest(
        symbol=symbol, exchange="EXCHANGE1", action=action,
        quantity=Decimal(qty), order_type="LIMIT", price=Decimal(price), product_type="DELIVERY",
    )


class TestOrders:
    """Tests for place_order."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_market_buy(self):
        route = respx.post(f"{BASE_URL}/openapi/v1/spot/order/create").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success", "data": 855188})
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker.close()

        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["symbol"] == "btcusdt"
        assert body["positionType"] == "market"
        assert body["quantity"] == "0.001"
        assert body["quantityUnit"] == "cont"

        assert resp.order_id == "855188"
        assert resp.status == "filled"
        assert resp.fill_price == Decimal("0")
        assert resp.fill_quantity == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_market_sell(self):
        route = respx.post(f"{BASE_URL}/openapi/v1/spot/order/close").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success", "data": 855189})
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order(action="SELL"))
        await broker.close()

        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["symbol"] == "btcusdt"
        assert body["positionType"] == "market"
        assert body["closeNum"] == "0.001"
        assert "quantity" not in body

        assert resp.order_id == "855189"
        assert resp.status == "filled"

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_limit_buy(self):
        route = respx.post(f"{BASE_URL}/openapi/v1/spot/order/create").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success", "data": 855190})
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_limit_order())
        await broker.close()

        body = json.loads(route.calls[0].request.content)
        assert body["positionType"] == "limit"
        assert body["price"] == "66000.00"
        assert body["quantity"] == "0.001"

        assert resp.order_id == "855190"
        assert resp.status == "open"

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_limit_sell(self):
        route = respx.post(f"{BASE_URL}/openapi/v1/spot/order/close").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success", "data": 855191})
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_limit_order(action="SELL"))
        await broker.close()

        body = json.loads(route.calls[0].request.content)
        assert body["positionType"] == "limit"
        assert body["price"] == "66000.00"
        assert body["closeNum"] == "0.001"

        assert resp.order_id == "855191"
        assert resp.status == "open"

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_rejected(self):
        respx.post(f"{BASE_URL}/openapi/v1/spot/order/create").mock(
            return_value=httpx.Response(200, json={"code": 400, "msg": "Insufficient balance"})
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker.close()

        assert resp.status == "rejected"
        assert "Insufficient balance" in resp.message

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_http_error(self):
        respx.post(f"{BASE_URL}/openapi/v1/spot/order/create").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        broker = _make_authenticated_broker()
        resp = await broker.place_order(_market_order())
        await broker.close()

        assert resp.status == "rejected"
        assert "500" in resp.message


# ---------------------------------------------------------------------------
# Cancel & Status
# ---------------------------------------------------------------------------


class TestCancelAndStatus:
    """Tests for cancel_order and get_order_status."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_cancel_order_success(self):
        route = respx.post(f"{BASE_URL}/openapi/v1/spot/order/cancel").mock(
            return_value=httpx.Response(200, json={"code": 200, "msg": "success"})
        )

        broker = _make_authenticated_broker()
        result = await broker.cancel_order("855188")
        await broker.close()

        assert result is True
        body = json.loads(route.calls[0].request.content)
        assert body["id"] == "855188"

    @respx.mock
    @pytest.mark.asyncio
    async def test_cancel_order_failure(self):
        respx.post(f"{BASE_URL}/openapi/v1/spot/order/cancel").mock(
            return_value=httpx.Response(200, json={"code": 400, "msg": "Order already filled"})
        )

        broker = _make_authenticated_broker()
        with pytest.raises(RuntimeError, match="Order already filled"):
            await broker.cancel_order("855188")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status_filled(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {
                    "id": "855188",
                    "state": "filled",
                    "tradePrice": "66500.00",
                    "doneQuantity": "0.001",
                    "quantity": "0.001",
                },
            })
        )

        broker = _make_authenticated_broker()
        status = await broker.get_order_status("855188")
        await broker.close()

        assert status.order_id == "855188"
        assert status.status == "filled"
        assert status.fill_price == Decimal("66500.00")
        assert status.fill_quantity == Decimal("0.001")
        assert status.pending_quantity == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status_partially_filled(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {
                    "id": "855188",
                    "state": "partially_filled",
                    "estimatedPrice": "66000.00",
                    "doneQuantity": "0.0005",
                    "quantity": "0.001",
                },
            })
        )

        broker = _make_authenticated_broker()
        status = await broker.get_order_status("855188")
        await broker.close()

        assert status.status == "open"
        assert status.fill_price == Decimal("66000.00")
        assert status.fill_quantity == Decimal("0.0005")
        assert status.pending_quantity == Decimal("0.0005")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status_cancelled(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {
                    "id": "855188",
                    "state": "canceled",
                    "quantity": "0.001",
                },
            })
        )

        broker = _make_authenticated_broker()
        status = await broker.get_order_status("855188")
        await broker.close()

        assert status.status == "cancelled"
        assert status.fill_price == Decimal("0")
        assert status.fill_quantity == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status_unknown_state_defaults_to_open(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {
                    "id": "855188",
                    "state": "some_new_state",
                    "quantity": "0.001",
                },
            })
        )

        broker = _make_authenticated_broker()
        status = await broker.get_order_status("855188")
        await broker.close()

        assert status.status == "open"


# ---------------------------------------------------------------------------
# Portfolio / Balance
# ---------------------------------------------------------------------------

_BALANCE_RESPONSE = {
    "code": 200,
    "data": [
        {"currency": "USDT", "available": "5000.00", "hold": "1000.00", "total": "6000.00"},
        {"currency": "BTC", "available": "0.5", "hold": "0.1", "total": "0.6"},
        {"currency": "ETH", "available": "10.0", "hold": "0.0", "total": "10.0"},
        {"currency": "USDC", "available": "2000.00", "hold": "0.0", "total": "2000.00"},
        {"currency": "SOL", "available": "0.0", "hold": "0.0", "total": "0.0"},
    ],
}


class TestPortfolio:
    """Tests for get_balance, get_positions, get_holdings, and account caching."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_balance_extracts_usdt(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
        )

        broker = _make_authenticated_broker()
        balance = await broker.get_balance()
        await broker.close()

        assert balance.available == Decimal("5000.00")
        assert balance.used_margin == Decimal("1000.00")
        assert balance.total == Decimal("6000.00")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_excludes_quote_and_zero(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()
        await broker.close()

        symbols = {p.symbol for p in positions}
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "USDT" not in symbols
        assert "USDC" not in symbols
        assert "SOL" not in symbols  # zero balance

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_fields(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()
        await broker.close()

        btc = next(p for p in positions if p.symbol == "BTC")
        assert btc.quantity == Decimal("0.6")
        assert btc.exchange == "EXCHANGE1"
        assert btc.action == "BUY"
        assert btc.entry_price == Decimal("0")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_holdings(self):
        respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
        )

        broker = _make_authenticated_broker()
        holdings = await broker.get_holdings()
        await broker.close()

        symbols = {h.symbol for h in holdings}
        assert symbols == {"BTC", "ETH"}

        btc = next(h for h in holdings if h.symbol == "BTC")
        assert btc.quantity == Decimal("0.6")
        assert btc.exchange == "EXCHANGE1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_account_cache_prevents_duplicate_calls(self):
        route = respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
            return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
        )

        broker = _make_authenticated_broker()
        await broker.get_balance()
        await broker.get_positions()
        await broker.get_holdings()
        await broker.close()

        assert route.call_count == 1


# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------


class TestMarketData:
    """Tests for get_quotes and get_historical."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_quotes_single_symbol(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/orderbook").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {
                    "asks": [["66500.00", "1.5"], ["66600.00", "2.0"]],
                    "bids": [["66400.00", "1.0"], ["66300.00", "0.5"]],
                },
            })
        )

        broker = _make_authenticated_broker()
        quotes = await broker.get_quotes(["BTCUSDT"])
        await broker.close()

        assert len(quotes) == 1
        q = quotes[0]
        assert q.symbol == "BTCUSDT"
        assert q.exchange == "EXCHANGE1"
        assert q.bid == Decimal("66400.00")
        assert q.ask == Decimal("66500.00")
        assert q.last_price == (Decimal("66400.00") + Decimal("66500.00")) / 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_quotes_empty_orderbook_skipped(self):
        respx.get(f"{BASE_URL}/openapi/v1/spot/orderbook").mock(
            return_value=httpx.Response(200, json={
                "code": 200,
                "data": {"asks": [], "bids": []},
            })
        )

        broker = _make_authenticated_broker()
        quotes = await broker.get_quotes(["ILLIQUIDUSDT"])
        await broker.close()

        assert len(quotes) == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_historical_basic(self):
        candles = [
            [1700000000000, "30000.0", "30500.0", "29500.0", "30200.0", "100.5",
             1700000059999, "0", 0, "0", "0", "0"],
            [1700000060000, "30200.0", "30600.0", "30100.0", "30400.0", "200.3",
             1700000119999, "0", 0, "0", "0", "0"],
        ]
        respx.get(f"{BINANCE_URL}/api/v3/klines").mock(
            return_value=httpx.Response(200, json=candles)
        )

        broker = _make_authenticated_broker()
        start = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        end = datetime(2023, 11, 14, 22, 15, 20, tzinfo=UTC)
        result = await broker.get_historical("BTCUSDT", "1m", start, end)
        await broker.close()

        assert len(result) == 2
        c0 = result[0]
        assert c0.open == Decimal("30000.0")
        assert c0.close == Decimal("30200.0")
        assert c0.volume == Decimal("100.5")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_historical_paginates(self):
        batch_1 = []
        for i in range(1000):
            open_time = 1700000000000 + i * 60000
            close_time = open_time + 59999
            batch_1.append([
                open_time, "30000.0", "30500.0", "29500.0", "30200.0", "100.0",
                close_time, "0", 0, "0", "0", "0",
            ])

        batch_2 = []
        last_close = batch_1[-1][6]
        for i in range(200):
            open_time = last_close + 1 + i * 60000
            close_time = open_time + 59999
            batch_2.append([
                open_time, "31000.0", "31500.0", "30500.0", "31200.0", "50.0",
                close_time, "0", 0, "0", "0", "0",
            ])

        route = respx.get(f"{BINANCE_URL}/api/v3/klines").mock(
            side_effect=[
                Response(200, json=batch_1),
                Response(200, json=batch_2),
            ]
        )

        broker = _make_authenticated_broker()
        start = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        end = datetime(2023, 12, 1, 0, 0, 0, tzinfo=UTC)
        result = await broker.get_historical("BTCUSDT", "1m", start, end)
        await broker.close()

        assert len(result) == 1200
        assert route.call_count == 2
