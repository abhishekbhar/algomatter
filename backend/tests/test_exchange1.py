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
