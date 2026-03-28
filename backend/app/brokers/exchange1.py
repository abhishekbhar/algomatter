"""Exchange1 Global spot broker adapter.

Provides live spot trading against Exchange1 Global (https://www.exchange1.global)
with RSA (SHA256WithRSA) request signing and full BrokerAdapter compliance.
Historical kline data falls back to Binance public API since Exchange1
only provides klines via WebSocket.
"""

from __future__ import annotations

import base64
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

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

BASE_URL = "https://www.exchange1.global"
BINANCE_URL = "https://api.binance.com"
QUOTE_ASSETS: set[str] = {"USDT", "USDC"}

_STATUS_MAP: dict[str, str] = {
    "new": "open",
    "partially_filled": "open",
    "filled": "filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "rejected": "rejected",
    "expired": "cancelled",
}


class Exchange1Broker(BrokerAdapter):
    """Adapter for Exchange1 Global spot trading.

    Parameters are injected via :meth:`authenticate` rather than ``__init__``
    so that the broker can be constructed before credentials are available.
    """

    def __init__(self) -> None:
        self._api_key: str = ""
        self._private_key: str = ""
        self._private_key_obj: Any = None
        self._recv_window: str = "5000"
        self._client: httpx.AsyncClient | None = None
        self._binance_client: httpx.AsyncClient | None = None
        self._account_cache: tuple[float, list[dict]] | None = None

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------

    def _build_signed_headers(self, params: dict) -> dict[str, str]:
        """Build all required auth headers for a signed request.

        Returns a dict with X-SAASAPI-API-KEY, X-SAASAPI-TIMESTAMP,
        X-SAASAPI-RECV-WINDOW, X-SAASAPI-SIGN, and Content-Type.
        """
        timestamp = str(int(time.time() * 1000))
        filtered = {k: v for k, v in params.items() if v is not None and v != ""}
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
        payload = f"{timestamp}{self._api_key}{self._recv_window}{sorted_params}"

        signature = self._private_key_obj.sign(
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return {
            "X-SAASAPI-API-KEY": self._api_key,
            "X-SAASAPI-TIMESTAMP": timestamp,
            "X-SAASAPI-RECV-WINDOW": self._recv_window,
            "X-SAASAPI-SIGN": base64.b64encode(signature).decode(),
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> dict:
        assert self._client is not None, "Client not initialised; call authenticate() first"
        params = dict(params or {})
        headers: dict[str, str] = {}
        if signed:
            headers = self._build_signed_headers(params)
        resp = await self._client.get(f"{BASE_URL}{path}", params=params, headers=headers)
        return self._check_response(resp)

    async def _post(self, path: str, body: dict[str, Any] | None = None, signed: bool = False) -> dict:
        assert self._client is not None, "Client not initialised; call authenticate() first"
        body = dict(body or {})
        headers: dict[str, str] = {}
        if signed:
            headers = self._build_signed_headers(body)
        resp = await self._client.post(f"{BASE_URL}{path}", json=body, headers=headers)
        return self._check_response(resp)

    def _check_response(self, resp: httpx.Response) -> dict:
        if resp.status_code == 429:
            logger.warning("exchange1_rate_limited", status=resp.status_code, url=str(resp.url))
        if resp.status_code >= 400:
            raise RuntimeError(f"Exchange1 API error {resp.status_code}: {resp.text}")
        data = resp.json()
        if isinstance(data, dict) and data.get("code") not in (None, 200):
            raise RuntimeError(f"Exchange1 error code={data.get('code')}: {data.get('msg', '')}")
        return data

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:
        self._api_key = credentials["api_key"]
        self._private_key = credentials["private_key"]
        self._private_key_obj = serialization.load_pem_private_key(
            self._private_key.encode(), password=None
        )
        self._client = httpx.AsyncClient(timeout=10.0)
        try:
            await self._post("/openapi/v1/token", body={}, signed=True)
        except RuntimeError:
            return False
        return True

    async def verify_connection(self) -> bool:
        try:
            await self._get("/openapi/v1/balance", signed=True)
        except (RuntimeError, httpx.HTTPError):
            return False
        return True

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a spot order on Exchange1.

        BUY → POST /openapi/v1/spot/order/create
        SELL → POST /openapi/v1/spot/order/close
        """
        symbol = order.symbol.lower()
        position_type = "market" if order.order_type == "MARKET" else "limit"

        if order.action == "BUY":
            path = "/openapi/v1/spot/order/create"
            body: dict[str, Any] = {
                "symbol": symbol,
                "positionType": position_type,
                "quantity": str(order.quantity),
                "quantityUnit": "cont",
            }
        else:
            path = "/openapi/v1/spot/order/close"
            body = {
                "symbol": symbol,
                "positionType": position_type,
                "closeNum": str(order.quantity),
            }

        if order.order_type == "LIMIT":
            body["price"] = str(order.price)

        try:
            data = await self._post(path, body=body, signed=True)
        except RuntimeError as exc:
            return OrderResponse(order_id="", status="rejected", message=str(exc))

        order_id = str(data.get("data", ""))
        status = "filled" if order.order_type == "MARKET" else "open"

        return OrderResponse(
            order_id=order_id,
            status=status,
            fill_price=Decimal("0"),
            fill_quantity=Decimal("0"),
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order on Exchange1."""
        await self._post("/openapi/v1/spot/order/cancel", body={"id": order_id}, signed=True)
        return True

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Query the current status of an order on Exchange1."""
        data = await self._get(
            "/openapi/v1/spot/order/detail", params={"id": order_id}, signed=True,
        )
        detail = data.get("data", {})

        state = detail.get("state", "")
        status = _STATUS_MAP.get(state, "open")

        fill_price_raw = detail.get("tradePrice") or detail.get("estimatedPrice")
        fill_price = Decimal(str(fill_price_raw)) if fill_price_raw else Decimal("0")

        done_qty_raw = detail.get("doneQuantity")
        fill_quantity = Decimal(str(done_qty_raw)) if done_qty_raw else Decimal("0")

        total_qty_raw = detail.get("quantity", "0")
        total_quantity = Decimal(str(total_qty_raw))
        pending_quantity = total_quantity - fill_quantity if total_quantity > fill_quantity else Decimal("0")

        return OrderStatus(
            order_id=str(detail.get("id", order_id)),
            status=status,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            pending_quantity=pending_quantity,
        )

    async def _get_balance_data(self) -> list[dict]:
        """Fetch account balances with a 2-second TTL cache."""
        now = time.time()
        if self._account_cache and (now - self._account_cache[0]) < 2.0:
            return self._account_cache[1]
        data = await self._get("/openapi/v1/balance", signed=True)
        accounts = data.get("data", [])
        self._account_cache = (now, accounts)
        return accounts

    async def get_balance(self) -> AccountBalance:
        """Return USDT balance from Exchange1 account."""
        accounts = await self._get_balance_data()
        for acc in accounts:
            if acc.get("currency") == "USDT":
                return AccountBalance(
                    available=Decimal(str(acc.get("available", "0"))),
                    used_margin=Decimal(str(acc.get("hold", "0"))),
                    total=Decimal(str(acc.get("total", "0"))),
                )
        return AccountBalance(available=Decimal("0"), used_margin=Decimal("0"), total=Decimal("0"))

    async def get_positions(self) -> list[Position]:
        """Return non-quote, non-zero asset balances as positions."""
        accounts = await self._get_balance_data()
        positions: list[Position] = []
        for acc in accounts:
            currency = acc.get("currency", "")
            if currency in QUOTE_ASSETS:
                continue
            total = Decimal(str(acc.get("total", "0")))
            if total == 0:
                continue
            positions.append(
                Position(
                    symbol=currency,
                    exchange="EXCHANGE1",
                    action="BUY",
                    quantity=total,
                    entry_price=Decimal("0"),
                    product_type="DELIVERY",
                )
            )
        return positions

    async def get_holdings(self) -> list[Holding]:
        """Return non-quote, non-zero asset balances as holdings."""
        accounts = await self._get_balance_data()
        holdings: list[Holding] = []
        for acc in accounts:
            currency = acc.get("currency", "")
            if currency in QUOTE_ASSETS:
                continue
            total = Decimal(str(acc.get("total", "0")))
            if total == 0:
                continue
            holdings.append(
                Holding(
                    symbol=currency,
                    exchange="EXCHANGE1",
                    quantity=total,
                    average_price=Decimal("0"),
                )
            )
        return holdings

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        """Fetch orderbook for each symbol and return best bid/ask with mid price."""
        quotes: list[Quote] = []
        for symbol in symbols:
            try:
                data = await self._get(
                    "/openapi/v1/spot/orderbook",
                    params={"symbol": symbol.lower()},
                )
            except RuntimeError:
                continue
            book = data.get("data", data)
            asks = book.get("asks", [])
            bids = book.get("bids", [])
            if not asks or not bids:
                continue
            best_ask = Decimal(str(asks[0][0]))
            best_bid = Decimal(str(bids[0][0]))
            mid_price = (best_ask + best_bid) / 2
            quotes.append(
                Quote(
                    symbol=symbol,
                    exchange="EXCHANGE1",
                    last_price=mid_price,
                    bid=best_bid,
                    ask=best_ask,
                )
            )
        return quotes

    async def get_historical(
        self, symbol: str, interval: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        """Fetch historical klines from Binance public API (Exchange1 fallback).

        Exchange1 only provides klines via WebSocket, so we use Binance's
        public REST API which requires no authentication.
        """
        if self._binance_client is None:
            self._binance_client = httpx.AsyncClient(timeout=10.0)

        all_candles: list[OHLCV] = []
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        while start_ms < end_ms:
            resp = await self._binance_client.get(
                f"{BINANCE_URL}/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break

            for candle in data:
                all_candles.append(OHLCV(
                    timestamp=datetime.fromtimestamp(candle[0] / 1000, tz=UTC),
                    open=Decimal(str(candle[1])),
                    high=Decimal(str(candle[2])),
                    low=Decimal(str(candle[3])),
                    close=Decimal(str(candle[4])),
                    volume=Decimal(str(candle[5])),
                ))

            if len(data) < 1000:
                break
            start_ms = data[-1][6] + 1  # closeTime + 1ms

        return all_candles

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._binance_client is not None:
            await self._binance_client.aclose()
            self._binance_client = None
        self._api_key = ""
        self._private_key = ""
        self._private_key_obj = None
        self._account_cache = None
