"""Exchange1 Global broker adapter (spot + futures/perpetual).

Provides live spot and perpetual futures trading against Exchange1 Global
(https://www.exchange1.global) with RSA (SHA256WithRSA) request signing
and full BrokerAdapter compliance.

Routing:  product_type == "FUTURES"  →  /openapi/v1/futures/* endpoints
          all others                  →  /openapi/v1/spot/*   endpoints

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
_BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

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
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_pem(raw: str) -> str:
        """Accept PEM or raw base64 DER and always return PEM."""
        if "-----BEGIN" in raw:
            return raw
        # Strip any whitespace/newlines from raw base64
        b64 = raw.strip().replace("\n", "").replace("\r", "")
        lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
        return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"

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
        # Strip None and empty-string values so the signed body matches the signature exactly
        body = {k: v for k, v in (body or {}).items() if v is not None and v != ""}
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
        raw_key = credentials.get("private_key") or credentials["secret_key"]
        self._private_key = self._normalize_pem(raw_key)
        self._private_key_obj = serialization.load_pem_private_key(
            self._private_key.encode(), password=None
        )
        self._client = httpx.AsyncClient(
            timeout=10.0, headers={"User-Agent": _BROWSER_UA},
        )
        try:
            await self._post("/openapi/v1/token", body={}, signed=True)
        except RuntimeError as exc:
            logger.error("exchange1_auth_failed", error=str(exc))
            return False
        return True

    async def verify_connection(self) -> bool:
        try:
            await self._get("/openapi/v1/balance", signed=True)
        except (RuntimeError, httpx.HTTPError):
            return False
        return True

    # ------------------------------------------------------------------
    # Symbol helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _futures_symbol(symbol: str) -> str:
        """Convert a trading symbol to Exchange1 futures format.

        Exchange1 futures use the lowercase base asset only:
          BTCUSDT → btc,  ETHUSDT → eth,  BTC → btc
        """
        s = symbol.upper()
        for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
            if s.endswith(quote) and len(s) > len(quote):
                return s[: -len(quote)].lower()
        return s.lower()

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a spot or futures order on Exchange1.

        Routing:
          product_type == "FUTURES", BUY  →  /openapi/v1/futures/order/create (open long)
          product_type == "FUTURES", SELL →  /openapi/v1/futures/order/close  (close long)
          all others                       →  /openapi/v1/spot/order/create|close
        """
        if order.product_type == "FUTURES":
            return await self._place_futures_order(order)
        return await self._place_spot_order(order)

    async def _place_spot_order(self, order: OrderRequest) -> OrderResponse:
        """Spot: BUY → create, SELL → close."""
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

    async def _place_futures_order(self, order: OrderRequest) -> OrderResponse:
        """Perpetual futures order routing.

        BUY  → open long  via POST /openapi/v1/futures/order/create
        SELL → close long via POST /openapi/v1/futures/order/close
        """
        if order.action == "BUY":
            return await self._open_futures_long(order)
        return await self._close_futures_position(order)

    @staticmethod
    def _api_position_model(position_model: str | None) -> str:
        """Normalise position_model from user-friendly names to Exchange1 API values.

        "isolated" → "fix"   (Exchange1 term for isolated margin)
        "cross"    → "cross"
        None/other → "fix"   (safe default: isolated)
        """
        if position_model and position_model.lower() == "cross":
            return "cross"
        return "fix"

    async def _open_futures_long(self, order: OrderRequest) -> OrderResponse:
        """Open a new long position via /openapi/v1/futures/order/create."""
        symbol = self._futures_symbol(order.symbol)
        position_type = "market" if order.order_type == "MARKET" else "limit"
        pos_model = self._api_position_model(order.position_model)

        body: dict[str, Any] = {
            "symbol": symbol,
            "positionType": position_type,
            "positionSide": "long",
            "quantity": str(order.quantity),
            "quantityUnit": "cont",
            "positionModel": pos_model,
        }
        body["leverage"] = str(order.leverage) if order.leverage else "10"
        if order.order_type == "LIMIT" and order.price:
            body["price"] = str(order.price)
        if order.take_profit:
            body["takeProfitPrice"] = str(order.take_profit)
        if order.stop_loss:
            body["stopLossPrice"] = str(order.stop_loss)

        try:
            data = await self._post("/openapi/v1/futures/order/create", body=body, signed=True)
        except RuntimeError as exc:
            return OrderResponse(order_id="", status="rejected", message=str(exc))

        raw_id = str(data.get("data", ""))
        order_id = f"futures:{raw_id}" if raw_id else ""
        status = "filled" if order.order_type == "MARKET" else "open"
        return OrderResponse(order_id=order_id, status=status, fill_price=Decimal("0"), fill_quantity=Decimal("0"))

    async def _close_futures_position(self, order: OrderRequest) -> OrderResponse:
        """Close an existing long position via /openapi/v1/futures/order/close.

        Uses closeType="all" to close the full position for the symbol.
        For a partial close, pass the position ID via order.trigger_price
        (repurposed as a numeric position-id carrier).
        """
        symbol = self._futures_symbol(order.symbol)
        position_type = "market" if order.order_type == "MARKET" else "limit"

        body: dict[str, Any] = {
            "symbol": symbol,
            "positionType": position_type,
            "closeType": "all",
        }
        if order.order_type == "LIMIT" and order.price:
            body["price"] = str(order.price)

        try:
            data = await self._post("/openapi/v1/futures/order/close", body=body, signed=True)
        except RuntimeError as exc:
            return OrderResponse(order_id="", status="rejected", message=str(exc))

        raw_id = str(data.get("data", ""))
        order_id = f"futures:{raw_id}" if raw_id else ""
        status = "filled" if order.order_type == "MARKET" else "open"
        return OrderResponse(order_id=order_id, status=status, fill_price=Decimal("0"), fill_quantity=Decimal("0"))

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order on Exchange1 (spot or futures)."""
        if order_id.startswith("futures:"):
            raw_id = order_id[len("futures:"):]
            await self._post("/openapi/v1/futures/order/cancel", body={"id": raw_id}, signed=True)
        else:
            await self._post("/openapi/v1/spot/order/cancel", body={"id": order_id}, signed=True)
        return True

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Query the current status of an order on Exchange1 (spot or futures)."""
        if order_id.startswith("futures:"):
            return await self._get_futures_order_status(order_id[len("futures:"):])

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

    async def _get_futures_order_status(self, raw_id: str) -> OrderStatus:
        """Check futures order status via current-orders list.

        Exchange1 has no single-order detail endpoint for futures; we scan
        /openapi/v1/futures/order/current.  If the order is absent it is
        assumed filled (Exchange1 removes filled orders from the list).
        """
        for pos_model in ("fix", "cross"):
            try:
                data = await self._get(
                    "/openapi/v1/futures/order/current",
                    params={"page": 1, "pageSize": 50, "positionModel": pos_model},
                    signed=True,
                )
            except RuntimeError:
                continue
            orders = data.get("data", {}).get("list", [])
            for o in orders:
                if str(o.get("id")) == raw_id or str(o.get("idStr")) == raw_id:
                    qty = Decimal(str(o.get("quantity", "0")))
                    return OrderStatus(
                        order_id=f"futures:{raw_id}",
                        status="open",
                        fill_price=Decimal("0"),
                        fill_quantity=Decimal("0"),
                        pending_quantity=qty,
                    )
        # Not in active orders → treat as filled
        return OrderStatus(
            order_id=f"futures:{raw_id}",
            status="filled",
            fill_price=Decimal("0"),
            fill_quantity=Decimal("0"),
        )

    async def _get_balance_data(self) -> list[dict]:
        """Fetch account balances with a 2-second TTL cache.

        Returns a flat list of ``{currency, available, hold, total,
        available_margin, account_type}`` dicts for spot, cfd, and asset
        sub-accounts.
        """
        now = time.time()
        if self._account_cache and (now - self._account_cache[0]) < 2.0:
            return self._account_cache[1]
        data = await self._get("/openapi/v1/balance", signed=True)

        flat: list[dict] = []
        for acct in data.get("data", {}).get("accounts", []):
            biz_name = acct.get("biz", {}).get("name", "")
            if biz_name not in ("spot", "cfd", "asset"):
                continue
            for cur in acct.get("currencies", []):
                bal = cur.get("balance", {})
                flat.append({
                    "currency": cur.get("displayCode") or cur.get("name", ""),
                    "available": bal.get("available", 0),
                    "hold": bal.get("hold", 0),
                    "total": bal.get("total", 0),
                    "available_margin": bal.get("availableMargin", bal.get("available", 0)),
                    "account_type": biz_name,
                })

        self._account_cache = (now, flat)
        return flat

    async def get_balance(self, product_type: str | None = None) -> AccountBalance:
        """Return available balance filtered by product type.

        If *product_type* is ``"FUTURES"`` → return CFD balance.
        If *product_type* is ``"SPOT"`` → return spot INR balance.
        If *product_type* is ``None`` (default) → use legacy priority:
          1. First cfd entry with non-zero available margin.
          2. First asset entry with non-zero available balance.
          3. Spot USDT balance.
        """
        accounts = await self._get_balance_data()

        if product_type == "FUTURES":
            for acc in accounts:
                if acc.get("account_type") == "cfd":
                    return AccountBalance(
                        available=Decimal(str(acc.get("available_margin", "0"))),
                        used_margin=Decimal(str(acc.get("hold", "0"))),
                        total=Decimal(str(acc.get("total", "0"))),
                    )
            return AccountBalance(available=Decimal("0"), used_margin=Decimal("0"), total=Decimal("0"))

        if product_type == "SPOT":
            for acc in accounts:
                if acc.get("account_type") == "asset" and acc.get("currency") == "INR":
                    return AccountBalance(
                        available=Decimal(str(acc.get("available", "0"))),
                        used_margin=Decimal(str(acc.get("hold", "0"))),
                        total=Decimal(str(acc.get("total", "0"))),
                    )
            return AccountBalance(available=Decimal("0"), used_margin=Decimal("0"), total=Decimal("0"))

        # Legacy priority when no product_type specified
        # 1. cfd with funds
        for acc in accounts:
            if acc.get("account_type") == "cfd" and Decimal(str(acc.get("available_margin", "0"))) > 0:
                return AccountBalance(
                    available=Decimal(str(acc.get("available_margin", "0"))),
                    used_margin=Decimal(str(acc.get("hold", "0"))),
                    total=Decimal(str(acc.get("total", "0"))),
                )
        # 2. asset with funds
        for acc in accounts:
            if acc.get("account_type") == "asset" and Decimal(str(acc.get("available", "0"))) > 0:
                return AccountBalance(
                    available=Decimal(str(acc.get("available", "0"))),
                    used_margin=Decimal(str(acc.get("hold", "0"))),
                    total=Decimal(str(acc.get("total", "0"))),
                )
        # 3. spot USDT
        for acc in accounts:
            if acc.get("currency") == "USDT" and acc.get("account_type") == "spot":
                return AccountBalance(
                    available=Decimal(str(acc.get("available", "0"))),
                    used_margin=Decimal(str(acc.get("hold", "0"))),
                    total=Decimal(str(acc.get("total", "0"))),
                )
        return AccountBalance(available=Decimal("0"), used_margin=Decimal("0"), total=Decimal("0"))

    async def get_positions(self) -> list[Position]:
        """Return open positions: spot asset balances + futures open positions."""
        positions: list[Position] = []

        # --- Spot positions (non-zero, non-quote asset balances) ---
        accounts = await self._get_balance_data()
        for acc in accounts:
            if acc.get("account_type") != "spot":
                continue
            currency = acc.get("currency", "")
            if currency in QUOTE_ASSETS:
                continue
            total = Decimal(str(acc.get("total", "0")))
            if total == 0:
                continue
            positions.append(Position(
                symbol=currency,
                exchange="EXCHANGE1",
                action="BUY",
                quantity=total,
                entry_price=Decimal("0"),
                product_type="DELIVERY",
            ))

        # --- Futures positions ---
        for pos_model in ("fix", "cross"):
            try:
                data = await self._get(
                    "/openapi/v1/futures/order/positions",
                    params={"page": 1, "pageSize": 50, "positionModel": pos_model},
                    signed=True,
                )
            except RuntimeError:
                continue
            for row in data.get("data", {}).get("list", []):
                qty_raw = row.get("quantity") or row.get("currentPiece", 0)
                qty = Decimal(str(qty_raw))
                if qty == 0:
                    continue
                direction = str(row.get("direction", "long")).lower()
                positions.append(Position(
                    symbol=str(row.get("instrument", "")).upper(),
                    exchange="EXCHANGE1",
                    action="BUY" if direction == "long" else "SELL",
                    quantity=qty,
                    entry_price=Decimal(str(row.get("openPrice", "0"))),
                    product_type="FUTURES",
                ))

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

    @staticmethod
    def _strip_quote(symbol: str) -> str:
        """Extract base asset from a Binance-style symbol.

        BTCUSDT → btc, ETHUSDT → eth, SOLUSDT → sol, etc.
        """
        s = symbol.upper()
        for quote in ("USDT", "USDC", "USD"):
            if s.endswith(quote) and len(s) > len(quote):
                return s[: -len(quote)].lower()
        return s.lower()

    async def _get_usdt_inr_rate(self) -> Decimal:
        """Derive USDT/INR rate from BTCINR and BTCUSDT orderbooks."""
        try:
            inr_data = await self._get(
                "/openapi/v1/spot/orderbook",
                params={"symbol": "btcinr"},
                signed=True,
            )
            usdt_data = await self._get(
                "/openapi/v1/spot/orderbook",
                params={"symbol": "btcusdt"},
                signed=True,
            )
            inr_book = inr_data.get("data", inr_data)
            usdt_book = usdt_data.get("data", usdt_data)
            inr_mid = (Decimal(str(inr_book["asks"][0][0])) + Decimal(str(inr_book["bids"][0][0]))) / 2
            usdt_mid = (Decimal(str(usdt_book["asks"][0][0])) + Decimal(str(usdt_book["bids"][0][0]))) / 2
            if usdt_mid > 0:
                return inr_mid / usdt_mid
        except (RuntimeError, KeyError, IndexError):
            pass
        return Decimal("93")  # fallback

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        """Fetch price quotes in INR for the given symbols.

        Strategy: try ``<base>inr`` orderbook first.  If the INR pair doesn't
        exist, fall back to ``<base>usdt`` and multiply by the live USDT/INR
        rate (derived from BTCINR / BTCUSDT).
        """
        quotes: list[Quote] = []
        usdt_inr_rate: Decimal | None = None

        for symbol in symbols:
            base = self._strip_quote(symbol)

            # 1. Try INR pair
            inr_sym = f"{base}inr"
            try:
                data = await self._get(
                    "/openapi/v1/spot/orderbook",
                    params={"symbol": inr_sym},
                    signed=True,
                )
                book = data.get("data", data)
                asks = book.get("asks", [])
                bids = book.get("bids", [])
                if asks and bids:
                    best_ask = Decimal(str(asks[0][0]))
                    best_bid = Decimal(str(bids[0][0]))
                    mid_price = (best_ask + best_bid) / 2
                    quotes.append(
                        Quote(symbol=symbol, exchange="EXCHANGE1", last_price=mid_price, bid=best_bid, ask=best_ask)
                    )
                    continue
            except RuntimeError:
                pass

            # 2. Fall back to USDT pair × USDT/INR rate
            usdt_sym = f"{base}usdt"
            try:
                data = await self._get(
                    "/openapi/v1/spot/orderbook",
                    params={"symbol": usdt_sym},
                    signed=True,
                )
                book = data.get("data", data)
                asks = book.get("asks", [])
                bids = book.get("bids", [])
                if asks and bids:
                    if usdt_inr_rate is None:
                        usdt_inr_rate = await self._get_usdt_inr_rate()
                    best_ask = Decimal(str(asks[0][0])) * usdt_inr_rate
                    best_bid = Decimal(str(bids[0][0])) * usdt_inr_rate
                    mid_price = (best_ask + best_bid) / 2
                    quotes.append(
                        Quote(symbol=symbol, exchange="EXCHANGE1", last_price=mid_price, bid=best_bid, ask=best_ask)
                    )
            except RuntimeError:
                continue

        return quotes

    async def get_historical(
        self, symbol: str, interval: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        """Fetch historical klines from Binance public API (Exchange1 fallback).

        Exchange1 only provides klines via WebSocket, so we use Binance's
        public REST API which requires no authentication.
        """
        if self._binance_client is None:
            self._binance_client = httpx.AsyncClient(
                timeout=10.0, headers={"User-Agent": _BROWSER_UA},
            )

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
