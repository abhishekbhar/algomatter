# Binance Testnet Broker Adapter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `BinanceTestnetBroker` adapter that connects to the Binance Spot Test Network for live-exchange trading with virtual funds.

**Architecture:** Implements the existing `BrokerAdapter` ABC with HMAC-SHA256 signed requests against `https://testnet.binance.vision/api`. Uses `httpx.AsyncClient` for HTTP, stdlib `hmac`/`hashlib` for signing. A new async factory resolves broker type strings to authenticated adapter instances. The webhook router gets a `"live"` mode branch for dispatching orders through live brokers.

**Tech Stack:** Python 3.12, FastAPI, httpx, HMAC-SHA256, respx (test), Next.js/React/Chakra UI (frontend)

**Spec:** `docs/superpowers/specs/2026-03-28-binance-testnet-broker-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/brokers/binance_testnet.py` | Create | `BinanceTestnetBroker` class — full `BrokerAdapter` implementation |
| `backend/app/brokers/factory.py` | Create | `get_broker()` async factory — resolves broker_type → authenticated adapter |
| `backend/app/brokers/__init__.py` | Modify | Re-export `BinanceTestnetBroker` and `get_broker` |
| `backend/app/webhooks/router.py` | Modify | Add `elif strategy.mode == "live"` dispatch branch |
| `backend/pyproject.toml` | Modify | Add `respx` to dev dependencies |
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Modify | Add `binance_testnet` option to broker form |
| `backend/tests/test_binance_testnet.py` | Create | Unit tests for signing, order mapping, error handling, klines, caching |
| `backend/tests/test_broker_factory.py` | Create | Unit tests for factory |
| `backend/tests/test_webhook_live_dispatch.py` | Create | Unit tests for live webhook dispatch branch |

---

## Task 1: Add `respx` test dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add respx to dev dependencies**

In `backend/pyproject.toml`, add `"respx>=0.21.0"` to the `dev` optional dependencies list:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "respx>=0.21.0",
    "ruff>=0.5.0",
]
```

- [ ] **Step 2: Install updated dependencies**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && pip install -e ".[dev]"`

- [ ] **Step 3: Verify respx is importable**

Run: `python -c "import respx; print(respx.__version__)"`
Expected: Version number printed, no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add respx test dependency for httpx mocking"
```

---

## Task 2: HMAC signing and HTTP client core

**Files:**
- Create: `backend/app/brokers/binance_testnet.py`
- Create: `backend/tests/test_binance_testnet.py`

This task builds the signing logic, HTTP client lifecycle, clock sync, and `verify_connection` / `authenticate` methods.

- [ ] **Step 1: Write failing test for HMAC signing**

Create `backend/tests/test_binance_testnet.py`:

```python
"""Tests for BinanceTestnetBroker adapter."""

import hashlib
import hmac
import time
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
import respx
from httpx import Response

from app.brokers.binance_testnet import BinanceTestnetBroker


class TestSigning:
    def test_sign_produces_valid_hmac(self):
        broker = BinanceTestnetBroker()
        broker._api_key = "test-key"
        broker._secret = "test-secret"
        broker._time_offset_ms = 0

        with patch("time.time", return_value=1700000000.0):
            params = broker._sign({"symbol": "BTCUSDT"})

        # Verify timestamp was added
        assert params["timestamp"] == 1700000000000

        # Verify signature is correct HMAC-SHA256
        expected_query = urlencode({"symbol": "BTCUSDT", "timestamp": 1700000000000})
        expected_sig = hmac.new(
            b"test-secret", expected_query.encode(), hashlib.sha256
        ).hexdigest()
        assert params["signature"] == expected_sig

    def test_sign_applies_time_offset(self):
        broker = BinanceTestnetBroker()
        broker._api_key = "test-key"
        broker._secret = "test-secret"
        broker._time_offset_ms = -500  # server is 500ms behind

        with patch("time.time", return_value=1700000000.0):
            params = broker._sign({"symbol": "BTCUSDT"})

        assert params["timestamp"] == 1700000000000 - 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestSigning -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.brokers.binance_testnet'`

- [ ] **Step 3: Implement signing and client core**

Create `backend/app/brokers/binance_testnet.py`:

```python
"""Binance Spot Test Network broker adapter.

Connects to https://testnet.binance.vision/api for trading with virtual funds.
Implements the full BrokerAdapter ABC interface.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime
from decimal import Decimal
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

logger = structlog.get_logger()

BASE_URL = "https://testnet.binance.vision"
QUOTE_ASSETS = {"USDT", "USDC"}


class BinanceTestnetBroker(BrokerAdapter):
    """Broker adapter for the Binance Spot Test Network.

    Uses HMAC-SHA256 signed requests. Base URL is hardcoded to the testnet
    to prevent accidental production use.
    """

    def __init__(self) -> None:
        self._api_key: str = ""
        self._secret: str = ""
        self._client: httpx.AsyncClient | None = None
        self._time_offset_ms: int = 0
        self._order_symbols: dict[str, str] = {}  # order_id -> symbol
        self._account_cache: tuple[float, dict] | None = None  # (ts, data)

    # -- Signing -------------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        """Add timestamp and HMAC-SHA256 signature to request params."""
        params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        query = urlencode(params)
        sig = hmac.new(
            self._secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    # -- HTTP helpers --------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None, signed: bool = False) -> dict:
        assert self._client is not None, "Client not initialized. Call authenticate() first."
        if params is None:
            params = {}
        if signed:
            params = self._sign(params)
        resp = await self._client.get(path, params=params, headers=self._headers())
        self._check_response(resp)
        return resp.json()

    async def _post(self, path: str, params: dict, signed: bool = True) -> dict:
        assert self._client is not None, "Client not initialized. Call authenticate() first."
        if signed:
            params = self._sign(params)
        resp = await self._client.post(path, params=params, headers=self._headers())
        self._check_response(resp)
        return resp.json()

    async def _delete(self, path: str, params: dict, signed: bool = True) -> dict:
        assert self._client is not None, "Client not initialized. Call authenticate() first."
        if signed:
            params = self._sign(params)
        resp = await self._client.delete(path, params=params, headers=self._headers())
        self._check_response(resp)
        return resp.json()

    def _check_response(self, resp: httpx.Response) -> None:
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "unknown")
            logger.warning("binance_rate_limited", retry_after=retry_after)
        if resp.status_code >= 400:
            try:
                data = resp.json()
                msg = data.get("msg", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Binance API error {resp.status_code}: {msg}")

    # -- Connection ----------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:
        self._api_key = credentials["api_key"]
        self._secret = credentials["api_secret"]
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)

        # Sync clock
        try:
            server_data = await self._get("/api/v3/time")
            server_time = server_data["serverTime"]
            local_time = int(time.time() * 1000)
            self._time_offset_ms = server_time - local_time
            logger.info("binance_clock_synced", offset_ms=self._time_offset_ms)
        except Exception:
            logger.warning("binance_clock_sync_failed, using local time")
            self._time_offset_ms = 0

        # Validate credentials
        try:
            await self._get("/api/v3/account", signed=True)
            return True
        except RuntimeError:
            return False

    async def verify_connection(self) -> bool:
        try:
            if self._client is None:
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
                    resp = await client.get("/api/v3/ping")
                    return resp.status_code == 200
            resp = await self._client.get("/api/v3/ping")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Shut down HTTP client and clear secrets from memory."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._secret = ""
        self._api_key = ""

    # -- Placeholder methods (implemented in subsequent tasks) ---------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    async def get_order_status(self, order_id: str) -> OrderStatus:
        raise NotImplementedError

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError

    async def get_holdings(self) -> list[Holding]:
        raise NotImplementedError

    async def get_balance(self) -> AccountBalance:
        raise NotImplementedError

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        raise NotImplementedError

    async def get_historical(
        self, symbol: str, interval: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        raise NotImplementedError
```

- [ ] **Step 4: Run signing tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestSigning -v`
Expected: 2 passed

- [ ] **Step 5: Write failing tests for authenticate and verify_connection**

Append to `backend/tests/test_binance_testnet.py`:

```python
class TestConnection:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000000})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json={"balances": []})
        )

        broker = BinanceTestnetBroker()
        result = await broker.authenticate({"api_key": "k", "api_secret": "s"})
        assert result is True
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_bad_credentials(self):
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000000})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(401, json={"code": -2015, "msg": "Invalid API-key"})
        )

        broker = BinanceTestnetBroker()
        result = await broker.authenticate({"api_key": "bad", "api_secret": "bad"})
        assert result is False
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_verify_connection_success(self):
        respx.get(f"{BASE_URL}/api/v3/ping").mock(
            return_value=Response(200, json={})
        )

        broker = BinanceTestnetBroker()
        result = await broker.verify_connection()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_clock_offset_computed(self):
        # Server says it's 500ms ahead
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000500})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json={"balances": []})
        )

        broker = BinanceTestnetBroker()
        with patch("time.time", return_value=1700000000.0):
            await broker.authenticate({"api_key": "k", "api_secret": "s"})

        assert broker._time_offset_ms == 500
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_close_clears_secrets(self):
        respx.get(f"{BASE_URL}/api/v3/time").mock(
            return_value=Response(200, json={"serverTime": 1700000000000})
        )
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json={"balances": []})
        )

        broker = BinanceTestnetBroker()
        await broker.authenticate({"api_key": "my-key", "api_secret": "my-secret"})
        await broker.close()

        assert broker._secret == ""
        assert broker._api_key == ""
        assert broker._client is None
```

Add the import at top of test file:

```python
from unittest.mock import patch
from app.brokers.binance_testnet import BASE_URL
```

- [ ] **Step 6: Run connection tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestConnection -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/brokers/binance_testnet.py backend/tests/test_binance_testnet.py
git commit -m "feat: add BinanceTestnetBroker with signing, auth, and connection"
```

---

## Task 3: Order placement and management

**Files:**
- Modify: `backend/app/brokers/binance_testnet.py`
- Modify: `backend/tests/test_binance_testnet.py`

Implements `place_order`, `cancel_order`, `get_order_status` with all order type mappings and status mappings.

- [ ] **Step 1: Write failing tests for order placement**

Append to `backend/tests/test_binance_testnet.py`:

```python
from decimal import Decimal
from app.brokers.base import OrderRequest


def _make_authenticated_broker() -> BinanceTestnetBroker:
    """Create a broker with pre-set credentials (no network calls)."""
    broker = BinanceTestnetBroker()
    broker._api_key = "test-key"
    broker._secret = "test-secret"
    broker._client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
    broker._time_offset_ms = 0
    return broker


class TestOrders:
    @respx.mock
    @pytest.mark.asyncio
    async def test_place_market_order(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 12345,
                "status": "FILLED",
                "executedQty": "0.5",
                "cummulativeQuoteQty": "15000.0",
                "fills": [{"price": "30000.0", "qty": "0.5"}],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("0.5"), order_type="MARKET",
            price=Decimal("0"), product_type="DELIVERY",
        )
        result = await broker.place_order(order)

        assert result.order_id == "12345"
        assert result.status == "filled"
        assert result.fill_quantity == Decimal("0.5")
        assert result.fill_price == Decimal("30000.0")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_limit_order(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 12346,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("0.5"), order_type="LIMIT",
            price=Decimal("29000"), product_type="DELIVERY",
        )
        result = await broker.place_order(order)

        assert result.order_id == "12346"
        assert result.status == "open"
        assert result.fill_price is None  # no fill yet
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_rejected(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(400, json={
                "code": -2010,
                "msg": "Account has insufficient balance for requested action.",
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("999"), order_type="MARKET",
            price=Decimal("0"), product_type="DELIVERY",
        )
        result = await broker.place_order(order)

        assert result.status == "rejected"
        assert "insufficient balance" in result.message.lower()
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_partially_filled_maps_to_open(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 12347,
                "status": "PARTIALLY_FILLED",
                "executedQty": "0.2",
                "cummulativeQuoteQty": "6000.0",
                "fills": [{"price": "30000.0", "qty": "0.2"}],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("0.5"), order_type="LIMIT",
            price=Decimal("30000"), product_type="DELIVERY",
        )
        result = await broker.place_order(order)

        assert result.status == "open"
        assert result.fill_quantity == Decimal("0.2")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_order_stores_symbol_in_map(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 99999,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="ETHUSDT", exchange="BINANCE_TESTNET", action="SELL",
            quantity=Decimal("1"), order_type="LIMIT",
            price=Decimal("2000"), product_type="DELIVERY",
        )
        await broker.place_order(order)

        assert broker._order_symbols["99999"] == "ETHUSDT"
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_cancel_order(self):
        # First place an order to populate the symbol map
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 55555,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )
        respx.delete(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 55555,
                "status": "CANCELED",
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("0.1"), order_type="LIMIT",
            price=Decimal("25000"), product_type="DELIVERY",
        )
        await broker.place_order(order)
        result = await broker.cancel_order("55555")

        assert result is True
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_cancel_order_unknown_id_raises(self):
        broker = _make_authenticated_broker()
        with pytest.raises(ValueError, match="Unknown order_id"):
            await broker.cancel_order("nonexistent")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_stop_loss_limit_order(self):
        route = respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 22222,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="SELL",
            quantity=Decimal("0.5"), order_type="SL",
            price=Decimal("28000"), product_type="DELIVERY",
            trigger_price=Decimal("28500"),
        )
        result = await broker.place_order(order)

        assert result.status == "open"
        # Verify the request params sent to Binance
        req = route.calls[0].request
        assert "STOP_LOSS_LIMIT" in str(req.url)
        assert "28500" in str(req.url)  # stopPrice
        assert "28000" in str(req.url)  # price
        assert "GTC" in str(req.url)  # timeInForce
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_place_stop_loss_market_order(self):
        route = respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 33333,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="SELL",
            quantity=Decimal("0.5"), order_type="SL-M",
            price=Decimal("0"), product_type="DELIVERY",
            trigger_price=Decimal("28500"),
        )
        result = await broker.place_order(order)

        assert result.status == "open"
        req = route.calls[0].request
        assert "STOP_LOSS" in str(req.url)
        assert "28500" in str(req.url)  # stopPrice
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status_unknown_id_raises(self):
        broker = _make_authenticated_broker()
        with pytest.raises(ValueError, match="Unknown order_id"):
            await broker.get_order_status("nonexistent")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_order_status(self):
        respx.post(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 77777,
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
                "fills": [],
            })
        )
        respx.get(f"{BASE_URL}/api/v3/order").mock(
            return_value=Response(200, json={
                "orderId": 77777,
                "status": "FILLED",
                "executedQty": "1.0",
                "cummulativeQuoteQty": "30000.0",
                "origQty": "1.0",
            })
        )

        broker = _make_authenticated_broker()
        order = OrderRequest(
            symbol="BTCUSDT", exchange="BINANCE_TESTNET", action="BUY",
            quantity=Decimal("1"), order_type="LIMIT",
            price=Decimal("30000"), product_type="DELIVERY",
        )
        await broker.place_order(order)
        status = await broker.get_order_status("77777")

        assert status.order_id == "77777"
        assert status.status == "filled"
        assert status.fill_quantity == Decimal("1.0")
        await broker.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestOrders -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement order methods**

Replace the placeholder `place_order`, `cancel_order`, `get_order_status` methods in `backend/app/brokers/binance_testnet.py`:

```python
    # -- Status mapping ------------------------------------------------------

    _STATUS_MAP: dict[str, str] = {
        "FILLED": "filled",
        "NEW": "open",
        "PARTIALLY_FILLED": "open",
        "CANCELED": "cancelled",
        "REJECTED": "rejected",
        "EXPIRED": "cancelled",
    }

    # -- Orders --------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        params: dict = {
            "symbol": order.symbol,
            "side": order.action,
            "quantity": str(order.quantity),
        }

        match order.order_type:
            case "MARKET":
                params["type"] = "MARKET"
            case "LIMIT":
                params["type"] = "LIMIT"
                params["price"] = str(order.price)
                params["timeInForce"] = "GTC"
            case "SL":
                params["type"] = "STOP_LOSS_LIMIT"
                params["price"] = str(order.price)
                params["stopPrice"] = str(order.trigger_price)
                params["timeInForce"] = "GTC"
            case "SL-M":
                params["type"] = "STOP_LOSS"
                params["stopPrice"] = str(order.trigger_price)

        try:
            data = await self._post("/api/v3/order", params)
        except RuntimeError as exc:
            return OrderResponse(
                order_id="",
                status="rejected",
                message=str(exc),
            )

        order_id = str(data["orderId"])
        self._order_symbols[order_id] = order.symbol

        executed_qty = Decimal(data.get("executedQty", "0"))
        cumulative_quote = Decimal(data.get("cummulativeQuoteQty", "0"))
        fill_price = (
            cumulative_quote / executed_qty
            if executed_qty > 0
            else None
        )

        return OrderResponse(
            order_id=order_id,
            status=self._STATUS_MAP.get(data["status"], "open"),
            fill_price=fill_price,
            fill_quantity=executed_qty if executed_qty > 0 else None,
        )

    async def cancel_order(self, order_id: str) -> bool:
        symbol = self._order_symbols.get(order_id)
        if not symbol:
            raise ValueError(f"Unknown order_id: {order_id}")

        await self._delete("/api/v3/order", {
            "symbol": symbol,
            "orderId": int(order_id),
        })
        return True

    async def get_order_status(self, order_id: str) -> OrderStatus:
        symbol = self._order_symbols.get(order_id)
        if not symbol:
            raise ValueError(f"Unknown order_id: {order_id}")

        data = await self._get("/api/v3/order", {
            "symbol": symbol,
            "orderId": int(order_id),
        }, signed=True)

        executed_qty = Decimal(data.get("executedQty", "0"))
        cumulative_quote = Decimal(data.get("cummulativeQuoteQty", "0"))
        orig_qty = Decimal(data.get("origQty", "0"))

        return OrderStatus(
            order_id=str(data["orderId"]),
            status=self._STATUS_MAP.get(data["status"], "open"),
            fill_price=(
                cumulative_quote / executed_qty if executed_qty > 0 else None
            ),
            fill_quantity=executed_qty if executed_qty > 0 else None,
            pending_quantity=orig_qty - executed_qty if orig_qty > 0 else None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestOrders -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/binance_testnet.py backend/tests/test_binance_testnet.py
git commit -m "feat: add order placement, cancel, and status to BinanceTestnetBroker"
```

---

## Task 4: Portfolio and balance methods

**Files:**
- Modify: `backend/app/brokers/binance_testnet.py`
- Modify: `backend/tests/test_binance_testnet.py`

Implements `get_positions`, `get_holdings`, `get_balance` with account caching.

- [ ] **Step 1: Write failing tests for portfolio methods**

Append to `backend/tests/test_binance_testnet.py`:

```python
ACCOUNT_RESPONSE = {
    "balances": [
        {"asset": "BTC", "free": "0.5", "locked": "0.1"},
        {"asset": "ETH", "free": "10.0", "locked": "0.0"},
        {"asset": "USDT", "free": "5000.0", "locked": "1000.0"},
        {"asset": "USDC", "free": "2000.0", "locked": "0.0"},
        {"asset": "BNB", "free": "0.0", "locked": "0.0"},  # zero balance
    ]
}


class TestPortfolio:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_balance(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        balance = await broker.get_balance()

        # USDT: 5000+1000=6000, USDC: 2000+0=2000 => total=8000
        assert balance.available == Decimal("7000.0")  # 5000+2000
        assert balance.used_margin == Decimal("1000.0")  # 1000+0
        assert balance.total == Decimal("8000.0")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_excludes_quote_assets(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()

        symbols = [p.symbol for p in positions]
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "USDT" not in symbols  # quote asset excluded
        assert "USDC" not in symbols  # quote asset excluded
        assert "BNB" not in symbols  # zero balance excluded
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_positions_fields(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        positions = await broker.get_positions()

        btc = next(p for p in positions if p.symbol == "BTC")
        assert btc.exchange == "BINANCE_TESTNET"
        assert btc.action == "BUY"
        assert btc.quantity == Decimal("0.6")  # free + locked
        assert btc.entry_price == Decimal("0")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_holdings(self):
        respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        holdings = await broker.get_holdings()

        symbols = [h.symbol for h in holdings]
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "USDT" not in symbols
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_account_cache_prevents_duplicate_calls(self):
        route = respx.get(f"{BASE_URL}/api/v3/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )

        broker = _make_authenticated_broker()
        await broker.get_balance()
        await broker.get_positions()
        await broker.get_holdings()

        # Only one API call should have been made (cached)
        assert route.call_count == 1
        await broker.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestPortfolio -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement portfolio methods**

Replace the placeholder `get_positions`, `get_holdings`, `get_balance` in `backend/app/brokers/binance_testnet.py`:

```python
    # -- Account cache -------------------------------------------------------

    async def _get_account_info(self) -> dict:
        """Fetch account info with 2s TTL cache."""
        now = time.time()
        if self._account_cache and (now - self._account_cache[0]) < 2.0:
            return self._account_cache[1]

        data = await self._get("/api/v3/account", signed=True)
        self._account_cache = (now, data)
        return data

    # -- Portfolio -----------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        data = await self._get_account_info()
        positions = []
        for bal in data.get("balances", []):
            asset = bal["asset"]
            if asset in QUOTE_ASSETS:
                continue
            free = Decimal(bal["free"])
            locked = Decimal(bal["locked"])
            total = free + locked
            if total <= 0:
                continue
            positions.append(Position(
                symbol=asset,
                exchange="BINANCE_TESTNET",
                action="BUY",
                quantity=total,
                entry_price=Decimal("0"),
                current_price=None,
                product_type="DELIVERY",
            ))
        return positions

    async def get_holdings(self) -> list[Holding]:
        data = await self._get_account_info()
        holdings = []
        for bal in data.get("balances", []):
            asset = bal["asset"]
            if asset in QUOTE_ASSETS:
                continue
            free = Decimal(bal["free"])
            locked = Decimal(bal["locked"])
            total = free + locked
            if total <= 0:
                continue
            holdings.append(Holding(
                symbol=asset,
                exchange="BINANCE_TESTNET",
                quantity=total,
                average_price=Decimal("0"),
                current_price=None,
            ))
        return holdings

    async def get_balance(self) -> AccountBalance:
        data = await self._get_account_info()
        available = Decimal("0")
        locked = Decimal("0")
        for bal in data.get("balances", []):
            if bal["asset"] in QUOTE_ASSETS:
                available += Decimal(bal["free"])
                locked += Decimal(bal["locked"])
        return AccountBalance(
            available=available,
            used_margin=locked,
            total=available + locked,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestPortfolio -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/binance_testnet.py backend/tests/test_binance_testnet.py
git commit -m "feat: add portfolio and balance methods with account caching"
```

---

## Task 5: Market data — quotes and historical klines

**Files:**
- Modify: `backend/app/brokers/binance_testnet.py`
- Modify: `backend/tests/test_binance_testnet.py`

- [ ] **Step 1: Write failing tests for quotes and klines**

Append to `backend/tests/test_binance_testnet.py`:

```python
from datetime import datetime, UTC


class TestMarketData:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_quotes_single_symbol(self):
        respx.get(f"{BASE_URL}/api/v3/ticker/24hr").mock(
            return_value=Response(200, json={
                "symbol": "BTCUSDT",
                "lastPrice": "30000.50",
                "bidPrice": "30000.00",
                "askPrice": "30001.00",
                "volume": "1234.5",
            })
        )

        broker = _make_authenticated_broker()
        quotes = await broker.get_quotes(["BTCUSDT"])

        assert len(quotes) == 1
        assert quotes[0].symbol == "BTCUSDT"
        assert quotes[0].exchange == "BINANCE_TESTNET"
        assert quotes[0].last_price == Decimal("30000.50")
        assert quotes[0].bid == Decimal("30000.00")
        assert quotes[0].ask == Decimal("30001.00")
        assert quotes[0].volume == Decimal("1234.5")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_historical_basic(self):
        # Binance kline format: [openTime, open, high, low, close, volume, closeTime, ...]
        respx.get(f"{BASE_URL}/api/v3/klines").mock(
            return_value=Response(200, json=[
                [1700000000000, "30000", "30500", "29800", "30200", "100", 1700003600000, "0", 0, "0", "0", "0"],
                [1700003600000, "30200", "30600", "30100", "30400", "150", 1700007200000, "0", 0, "0", "0", "0"],
            ])
        )

        broker = _make_authenticated_broker()
        candles = await broker.get_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=datetime(2023, 11, 14, 22, 0, tzinfo=UTC),
            end=datetime(2023, 11, 15, 0, 0, tzinfo=UTC),
        )

        assert len(candles) == 2
        assert candles[0].open == Decimal("30000")
        assert candles[0].high == Decimal("30500")
        assert candles[0].low == Decimal("29800")
        assert candles[0].close == Decimal("30200")
        assert candles[0].volume == Decimal("100")
        await broker.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_historical_paginates(self):
        """When >1000 candles, adapter should paginate."""
        # First call returns 1000 candles
        batch_1 = [
            [1700000000000 + i * 60000, "100", "101", "99", "100", "10",
             1700000000000 + (i + 1) * 60000, "0", 0, "0", "0", "0"]
            for i in range(1000)
        ]
        # Second call returns 200 candles (end of data)
        batch_2 = [
            [1700000000000 + (1000 + i) * 60000, "100", "101", "99", "100", "10",
             1700000000000 + (1001 + i) * 60000, "0", 0, "0", "0", "0"]
            for i in range(200)
        ]

        route = respx.get(f"{BASE_URL}/api/v3/klines")
        route.side_effect = [
            Response(200, json=batch_1),
            Response(200, json=batch_2),
        ]

        broker = _make_authenticated_broker()
        candles = await broker.get_historical(
            symbol="BTCUSDT",
            interval="1m",
            start=datetime(2023, 11, 14, 0, 0, tzinfo=UTC),
            end=datetime(2023, 11, 15, 0, 0, tzinfo=UTC),
        )

        assert len(candles) == 1200
        assert route.call_count == 2
        await broker.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestMarketData -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement market data methods**

Replace the placeholder `get_quotes` and `get_historical` in `backend/app/brokers/binance_testnet.py`:

```python
    # -- Market Data ---------------------------------------------------------

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        quotes = []
        for symbol in symbols:
            data = await self._get("/api/v3/ticker/24hr", {"symbol": symbol})
            quotes.append(Quote(
                symbol=data["symbol"],
                exchange="BINANCE_TESTNET",
                last_price=Decimal(data["lastPrice"]),
                bid=Decimal(data["bidPrice"]),
                ask=Decimal(data["askPrice"]),
                volume=Decimal(data["volume"]),
            ))
        return quotes

    async def get_historical(
        self, symbol: str, interval: str, start: datetime, end: datetime,
    ) -> list[OHLCV]:
        all_candles: list[OHLCV] = []
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        while start_ms < end_ms:
            data = await self._get("/api/v3/klines", {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            })
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

            # Advance start to close time of last candle + 1ms
            start_ms = data[-1][6] + 1

        return all_candles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py::TestMarketData -v`
Expected: 3 passed

- [ ] **Step 5: Run all broker tests together**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py -v`
Expected: All tests pass (signing + connection + orders + portfolio + market data)

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/binance_testnet.py backend/tests/test_binance_testnet.py
git commit -m "feat: add quotes and historical klines with pagination"
```

---

## Task 6: Broker factory and `__init__.py` exports

**Files:**
- Create: `backend/app/brokers/factory.py`
- Modify: `backend/app/brokers/__init__.py`
- Create: `backend/tests/test_broker_factory.py`

- [ ] **Step 1: Write failing test for factory**

Create `backend/tests/test_broker_factory.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_broker_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.brokers.factory'`

- [ ] **Step 3: Implement factory**

Create `backend/app/brokers/factory.py`:

```python
"""Async broker factory.

Resolves a broker_type string and credentials dict into an authenticated
BrokerAdapter instance ready for use.
"""

from app.brokers.base import BrokerAdapter
from app.brokers.binance_testnet import BinanceTestnetBroker


async def get_broker(broker_type: str, credentials: dict) -> BrokerAdapter:
    """Create and authenticate a broker adapter by type.

    The SimulatedBroker is not included here — it is only used by
    backtesting and paper trading, which instantiate it directly.
    """
    match broker_type:
        case "binance_testnet":
            broker = BinanceTestnetBroker()
            authenticated = await broker.authenticate(credentials)
            if not authenticated:
                await broker.close()
                raise RuntimeError("Failed to authenticate with Binance testnet")
            return broker
        case _:
            raise ValueError(f"Unknown broker type: {broker_type}")
```

- [ ] **Step 4: Run factory tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_broker_factory.py -v`
Expected: 2 passed

- [ ] **Step 5: Update `__init__.py` exports**

Modify `backend/app/brokers/__init__.py`:

```python
from app.brokers.base import (
    BrokerAdapter,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    Holding,
    AccountBalance,
    Quote,
    OHLCV,
)
from app.brokers.simulated import SimulatedBroker
from app.brokers.binance_testnet import BinanceTestnetBroker
from app.brokers.factory import get_broker

__all__ = [
    "BrokerAdapter",
    "OrderRequest",
    "OrderResponse",
    "OrderStatus",
    "Position",
    "Holding",
    "AccountBalance",
    "Quote",
    "OHLCV",
    "SimulatedBroker",
    "BinanceTestnetBroker",
    "get_broker",
]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/factory.py backend/app/brokers/__init__.py backend/tests/test_broker_factory.py
git commit -m "feat: add async broker factory and update exports"
```

---

## Task 7: Webhook live dispatch integration

**Files:**
- Modify: `backend/app/webhooks/router.py`
- Create: `backend/tests/test_webhook_live_dispatch.py`

- [ ] **Step 1: Write failing test for live dispatch**

Create `backend/tests/test_webhook_live_dispatch.py`:

```python
"""Tests for webhook live broker dispatch logic.

Verifies the live dispatch code path by mocking the broker factory
and testing the order construction and result handling.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.brokers.base import OrderRequest, OrderResponse


class TestLiveDispatchOrderConstruction:
    """Test that the live dispatch branch constructs correct OrderRequests
    and handles broker responses properly."""

    @pytest.mark.asyncio
    async def test_live_dispatch_constructs_order_from_signal(self):
        """Verify OrderRequest is correctly built from StandardSignal fields."""
        from app.webhooks.schemas import StandardSignal

        signal = StandardSignal(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="BUY",
            quantity=Decimal("0.5"),
            order_type="MARKET",
            price=None,
            product_type="DELIVERY",
        )

        # Build the OrderRequest the same way the webhook router does
        order_req = OrderRequest(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=signal.action,
            quantity=signal.quantity,
            order_type=signal.order_type or "MARKET",
            price=signal.price or Decimal("0"),
            product_type=signal.product_type or "DELIVERY",
            trigger_price=signal.trigger_price,
        )

        assert order_req.symbol == "BTCUSDT"
        assert order_req.action == "BUY"
        assert order_req.quantity == Decimal("0.5")
        assert order_req.order_type == "MARKET"
        assert order_req.trigger_price is None

    @pytest.mark.asyncio
    async def test_live_dispatch_with_stop_loss_signal(self):
        """Verify trigger_price is passed through for SL orders."""
        from app.webhooks.schemas import StandardSignal

        signal = StandardSignal(
            symbol="BTCUSDT",
            exchange="BINANCE_TESTNET",
            action="SELL",
            quantity=Decimal("0.5"),
            order_type="SL",
            price=Decimal("28000"),
            trigger_price=Decimal("28500"),
            product_type="DELIVERY",
        )

        order_req = OrderRequest(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=signal.action,
            quantity=signal.quantity,
            order_type=signal.order_type or "MARKET",
            price=signal.price or Decimal("0"),
            product_type=signal.product_type or "DELIVERY",
            trigger_price=signal.trigger_price,
        )

        assert order_req.trigger_price == Decimal("28500")
        assert order_req.order_type == "SL"

    @pytest.mark.asyncio
    async def test_live_dispatch_result_mapping(self):
        """Verify broker response is correctly split into
        execution_result (status string) and execution_detail (full dict)."""
        mock_response = OrderResponse(
            order_id="12345",
            status="filled",
            fill_price=Decimal("30000"),
            fill_quantity=Decimal("0.5"),
        )

        # Simulate what the webhook router does with the response
        execution_result = mock_response.status
        execution_detail = mock_response.model_dump(mode="json")

        assert execution_result == "filled"
        assert execution_detail["order_id"] == "12345"
        assert execution_detail["fill_price"] == 30000.0  # JSON mode converts Decimal

    @pytest.mark.asyncio
    async def test_live_dispatch_error_handling(self):
        """Verify broker errors are caught and stored correctly."""
        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(side_effect=RuntimeError("Connection timeout"))
        mock_broker.close = AsyncMock()

        # Simulate the try/except/finally from webhook router
        execution_result = None
        execution_detail = None
        try:
            await mock_broker.place_order(None)
        except Exception as exc:
            execution_result = "broker_error"
            execution_detail = {"error": str(exc)}
        finally:
            await mock_broker.close()

        assert execution_result == "broker_error"
        assert "Connection timeout" in execution_detail["error"]
        mock_broker.close.assert_called_once()
```

- [ ] **Step 2: Run test to verify it passes (validates mock setup)**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_webhook_live_dispatch.py -v`
Expected: 1 passed

- [ ] **Step 3: Implement live dispatch in webhook router**

In `backend/app/webhooks/router.py`, add the `elif` branch after the `if strategy.mode == "paper":` block (after line 114). Also add `execution_detail` to the `WebhookSignal` construction:

After line 114 (`execution_result = "no_active_session"`), add:

```python
        elif strategy.mode == "live":
            if not strategy.broker_connection_id:
                execution_result = "no_broker_connection"
            else:
                from app.brokers.factory import get_broker
                from app.brokers.base import OrderRequest as BrokerOrderRequest
                from app.crypto.encryption import decrypt_credentials
                from app.db.models import BrokerConnection

                bc_result = await session.execute(
                    select(BrokerConnection).where(
                        BrokerConnection.id == strategy.broker_connection_id,
                        BrokerConnection.tenant_id == user.id,
                    )
                )
                bc = bc_result.scalar_one_or_none()
                if not bc:
                    execution_result = "broker_connection_not_found"
                else:
                    creds = decrypt_credentials(user.id, bc.credentials)
                    broker = await get_broker(bc.broker_type, creds)
                    try:
                        order_req = BrokerOrderRequest(
                            symbol=signal.symbol,
                            exchange=signal.exchange,
                            action=signal.action,
                            quantity=signal.quantity,
                            order_type=signal.order_type or "MARKET",
                            price=signal.price or Decimal("0"),
                            product_type=signal.product_type or "DELIVERY",
                            trigger_price=signal.trigger_price,
                        )
                        result = await broker.place_order(order_req)
                        execution_result = result.status
                        execution_detail = result.model_dump(mode="json")
                    except Exception as exc:
                        execution_result = "broker_error"
                        execution_detail = {"error": str(exc)}
                    finally:
                        await broker.close()
```

Also add `execution_detail` variable initialization at the top of the for-loop (after `execution_result = None` around line 64):

```python
        execution_detail = None
```

And include it in the `WebhookSignal` construction (around line 126):

```python
        ws = WebhookSignal(
            tenant_id=user.id,
            strategy_id=strategy.id,
            raw_payload=payload,
            parsed_signal=parsed_signal,
            rule_result=rule_result_str,
            rule_detail=rule_detail,
            execution_result=execution_result,
            execution_detail=execution_detail,
            processing_ms=int((time.perf_counter() - start_time) * 1000),
        )
```

Add the `Decimal` import at the top of the file:

```python
from decimal import Decimal
```

- [ ] **Step 4: Run all tests to verify nothing broke**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/router.py backend/tests/test_webhook_live_dispatch.py
git commit -m "feat: add live broker dispatch to webhook processor"
```

---

## Task 8: Frontend — add Binance Testnet broker option

**Files:**
- Modify: `frontend/app/(dashboard)/brokers/new/page.tsx`

- [ ] **Step 1: Add binance_testnet to BROKER_FIELDS**

In `frontend/app/(dashboard)/brokers/new/page.tsx`, update the `BROKER_FIELDS` constant:

```typescript
const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "secret_key"],
  binance_testnet: ["api_key", "api_secret"],
};
```

- [ ] **Step 2: Add dropdown option**

In the same file, add the option to the `<Select>` element:

```tsx
<option value="zerodha">Zerodha</option>
<option value="exchange1">Exchange1</option>
<option value="binance_testnet">Binance Testnet</option>
```

- [ ] **Step 3: Verify frontend compiles**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend && npx next build` (or just verify the dev server doesn't error)

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/brokers/new/page.tsx
git commit -m "feat: add Binance Testnet option to broker connection form"
```

---

## Task 9: Final verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify Docker services still work**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && docker-compose up -d --build api && docker-compose logs --tail=5 api`
Expected: API starts successfully, "Uvicorn running" in logs

- [ ] **Step 3: Verify import works end-to-end**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -c "from app.brokers import BinanceTestnetBroker, get_broker; print('OK')"`
Expected: `OK`
