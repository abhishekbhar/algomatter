"""Tests for Exchange1Broker — RSA signing, authentication, orders, portfolio, and market data."""

from __future__ import annotations

import base64
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
from app.brokers.exchange1 import BASE_URL, Exchange1Broker

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
        import json
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
        import json
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

        import json
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

        import json
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
