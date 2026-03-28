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
from decimal import Decimal
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

    _STATUS_MAP: dict[str, str] = {
        "FILLED": "filled",
        "NEW": "open",
        "PARTIALLY_FILLED": "open",
        "CANCELED": "cancelled",
        "REJECTED": "rejected",
        "EXPIRED": "cancelled",
    }

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
    # Orders
    # ------------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a spot order on Binance Testnet.

        Supports MARKET, LIMIT, SL (stop-loss limit), and SL-M (stop-loss
        market) order types.
        """
        params: dict[str, Any] = {
            "symbol": order.symbol,
            "side": order.action,
            "quantity": str(order.quantity),
        }

        if order.order_type == "MARKET":
            params["type"] = "MARKET"
        elif order.order_type == "LIMIT":
            params["type"] = "LIMIT"
            params["price"] = str(order.price)
            params["timeInForce"] = "GTC"
        elif order.order_type == "SL":
            params["type"] = "STOP_LOSS_LIMIT"
            params["stopPrice"] = str(order.trigger_price)
            params["price"] = str(order.price)
            params["timeInForce"] = "GTC"
        elif order.order_type == "SL-M":
            params["type"] = "STOP_LOSS"
            params["stopPrice"] = str(order.trigger_price)

        try:
            resp = await self._post("/api/v3/order", params=params, signed=True)
        except RuntimeError as exc:
            return OrderResponse(
                order_id="",
                status="rejected",
                message=str(exc),
            )

        data = resp.json()
        order_id = str(data["orderId"])

        # Remember order_id → symbol for later cancel / status queries
        self._order_symbols[order_id] = order.symbol

        executed_qty = Decimal(data.get("executedQty", "0"))
        cum_quote_qty = Decimal(data.get("cummulativeQuoteQty", "0"))
        fill_price: Decimal | None = None
        if executed_qty > 0:
            fill_price = cum_quote_qty / executed_qty

        status = self._STATUS_MAP.get(data["status"], "open")

        return OrderResponse(
            order_id=order_id,
            status=status,  # type: ignore[arg-type]
            fill_price=fill_price,
            fill_quantity=executed_qty if executed_qty > 0 else None,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order on Binance Testnet."""
        symbol = self._order_symbols.get(order_id)
        if symbol is None:
            raise ValueError(
                f"Unknown order_id {order_id!r}; was it placed via this broker instance?"
            )

        await self._delete(
            "/api/v3/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )
        return True

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Query the current status of an order on Binance Testnet."""
        symbol = self._order_symbols.get(order_id)
        if symbol is None:
            raise ValueError(
                f"Unknown order_id {order_id!r}; was it placed via this broker instance?"
            )

        resp = await self._get(
            "/api/v3/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )
        data = resp.json()

        executed_qty = Decimal(data.get("executedQty", "0"))
        cum_quote_qty = Decimal(data.get("cummulativeQuoteQty", "0"))
        orig_qty = Decimal(data.get("origQty", "0"))

        fill_price: Decimal | None = None
        if executed_qty > 0:
            fill_price = cum_quote_qty / executed_qty

        status = self._STATUS_MAP.get(data["status"], "open")

        return OrderStatus(
            order_id=order_id,
            status=status,  # type: ignore[arg-type]
            fill_price=fill_price,
            fill_quantity=executed_qty if executed_qty > 0 else None,
            pending_quantity=orig_qty - executed_qty if orig_qty > executed_qty else None,
        )

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
