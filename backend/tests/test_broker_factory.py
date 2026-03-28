"""Tests for broker factory."""

import pytest
import respx
from httpx import Response

from app.brokers.binance_testnet import BASE_URL


class TestBrokerFactory:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_broker_binance_testnet(self):
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000000})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json={"balances": []})
        )

        from app.brokers.factory import get_broker
        broker = await get_broker("binance_testnet", {"api_key": "k", "api_secret": "s"})

        assert broker is not None
        assert broker._api_key == "k"
        await broker.close()

    @pytest.mark.asyncio
    async def test_get_broker_unknown_type_raises(self):
        from app.brokers.factory import get_broker
        with pytest.raises(ValueError, match="Unknown broker type"):
            await get_broker("nonexistent", {})

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_broker_auth_failure_raises(self):
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000000})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(401, json={"code": -2015, "msg": "Invalid API-key"})
        )

        from app.brokers.factory import get_broker
        with pytest.raises(RuntimeError, match="Failed to authenticate"):
            await get_broker("binance_testnet", {"api_key": "bad", "api_secret": "bad"})
