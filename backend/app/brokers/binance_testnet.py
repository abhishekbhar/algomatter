"""Binance Testnet broker adapter.

Provides live trading against Binance's testnet (https://testnet.binance.vision)
with HMAC-SHA256 request signing, clock synchronisation, and full BrokerAdapter
compliance.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from app.brokers.base import (
    AccountBalance,
    BrokerAdapter,
    Holding,
    OHLCV,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    Quote,
)

logger = structlog.get_logger(__name__)

BASE_URL = "https://testnet.binance.vision"
QUOTE_ASSETS: set[str] = {"USDT", "USDC"}


class BinanceTestnetBroker(BrokerAdapter):
    """Adapter for the Binance Spot Testnet.

    Parameters are injected via :meth:`authenticate` rather than ``__init__``
    so that the broker can be constructed before credentials are available.
    """

    def __init__(self) -> None:
        self._api_key: str = ""
        self._secret: str = ""
        self._client: httpx.AsyncClient | None = None
        self._time_offset_ms: int = 0
        self._order_symbols: dict[str, str] = {}
        self._account_cache: tuple[float, dict] | None = None

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add ``timestamp`` and HMAC-SHA256 ``signature`` to *params*."""
        params = dict(params)  # shallow copy to avoid mutating caller
        timestamp_ms = int(time.time() * 1000) + self._time_offset_ms
        params["timestamp"] = timestamp_ms
        query_string = urlencode(params)
        signature = hmac.new(
            self._secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> httpx.Response:
        assert self._client is not None, "Client not initialised; call authenticate() first"
        params = dict(params or {})
        if signed:
            params = self._sign(params)
        resp = await self._client.get(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._headers(),
        )
        self._check_response(resp)
        return resp

    async def _post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> httpx.Response:
        assert self._client is not None, "Client not initialised; call authenticate() first"
        params = dict(params or {})
        if signed:
            params = self._sign(params)
        resp = await self._client.post(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._headers(),
        )
        self._check_response(resp)
        return resp

    async def _delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> httpx.Response:
        assert self._client is not None, "Client not initialised; call authenticate() first"
        params = dict(params or {})
        if signed:
            params = self._sign(params)
        resp = await self._client.delete(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._headers(),
        )
        self._check_response(resp)
        return resp

    def _check_response(self, resp: httpx.Response) -> None:
        if resp.status_code == 429:
            logger.warning(
                "binance_rate_limited",
                status=resp.status_code,
                url=str(resp.url),
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Binance API error {resp.status_code}: {resp.text}"
            )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:
        """Store API keys, create httpx client, sync clock, and validate.

        Expected *credentials* keys: ``api_key``, ``api_secret``.
        Returns ``True`` on success, ``False`` on bad credentials.
        """
        self._api_key = credentials.get("api_key", "")
        self._secret = credentials.get("api_secret", "")
        self._client = httpx.AsyncClient()

        try:
            # Clock synchronisation
            time_resp = await self._client.get(f"{BASE_URL}/api/v3/time")
            if time_resp.status_code == 200:
                server_time = time_resp.json()["serverTime"]
                local_time = int(time.time() * 1000)
                self._time_offset_ms = server_time - local_time

            # Validate credentials by hitting a signed endpoint
            await self._get("/api/v3/account", signed=True)
            return True
        except RuntimeError:
            # _check_response raised on 401/403/etc.
            return False

    async def verify_connection(self) -> bool:
        """Ping the exchange (unsigned, no auth required)."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/api/v3/ping")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Shut down the HTTP client and clear secrets."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._api_key = ""
        self._secret = ""
        self._time_offset_ms = 0
        self._account_cache = None

    # ------------------------------------------------------------------
    # Orders (placeholder)
    # ------------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        raise NotImplementedError("place_order not yet implemented for BinanceTestnetBroker")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("cancel_order not yet implemented for BinanceTestnetBroker")

    async def get_order_status(self, order_id: str) -> OrderStatus:
        raise NotImplementedError("get_order_status not yet implemented for BinanceTestnetBroker")

    # ------------------------------------------------------------------
    # Portfolio (placeholder)
    # ------------------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError("get_positions not yet implemented for BinanceTestnetBroker")

    async def get_holdings(self) -> list[Holding]:
        raise NotImplementedError("get_holdings not yet implemented for BinanceTestnetBroker")

    async def get_balance(self) -> AccountBalance:
        raise NotImplementedError("get_balance not yet implemented for BinanceTestnetBroker")

    # ------------------------------------------------------------------
    # Market Data (placeholder)
    # ------------------------------------------------------------------

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        raise NotImplementedError("get_quotes not yet implemented for BinanceTestnetBroker")

    async def get_historical(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCV]:
        raise NotImplementedError("get_historical not yet implemented for BinanceTestnetBroker")
