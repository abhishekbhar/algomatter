"""Tests for BinanceTestnetBroker — signing, authentication, and connection."""

from __future__ import annotations

import hashlib
import hmac
import time
from unittest.mock import patch

import httpx
import pytest
import respx

from app.brokers.binance_testnet import BASE_URL, BinanceTestnetBroker


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
