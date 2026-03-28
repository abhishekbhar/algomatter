# Exchange1 Spot Broker Adapter — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `Exchange1Broker` adapter that connects AlgoMatter to Exchange1 Global spot trading API with RSA signing, full `BrokerAdapter` ABC compliance, and Binance fallback for historical klines.

**Architecture:** Single new file `backend/app/brokers/exchange1.py` implementing `BrokerAdapter` ABC with RSA (SHA256WithRSA) request signing. Separate BUY/SELL endpoints for spot orders. Historical data delegates to Binance public API. Three existing files modified for wiring (factory, `__init__`, frontend dropdown). One new test file with `respx` mocking.

**Tech Stack:** Python 3.13, httpx, cryptography (RSA/PKCS1v15/SHA256), structlog, respx (tests), pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-28-exchange1-spot-broker-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/brokers/exchange1.py` | `Exchange1Broker` class — RSA signing, auth, orders, portfolio, quotes, historical (Binance fallback) |
| Create | `backend/tests/test_exchange1.py` | Unit tests with `respx` mocking for all Exchange1Broker methods |
| Modify | `backend/app/brokers/factory.py` | Add `"exchange1"` case to `get_broker()` match statement |
| Modify | `backend/app/brokers/__init__.py` | Re-export `Exchange1Broker` |
| Modify | `frontend/app/(dashboard)/brokers/new/page.tsx` | Fix credential field: `secret_key` → `private_key` |

---

### Task 1: RSA Signing & HTTP Helpers

**Files:**
- Create: `backend/app/brokers/exchange1.py` (partial — class skeleton, signing, HTTP helpers)
- Test: `backend/tests/test_exchange1.py` (partial — signing tests)

**Context:** Exchange1 uses RSA SHA256WithRSA signing, unlike Binance's HMAC-SHA256. The signature payload is `timestamp + api_key + recv_window + sorted_params`. Parameters are sorted by ASCII key order, empty/null values excluded. The signature is base64-encoded and sent in `X-SAASAPI-SIGN` header. See spec section "Authentication & Signing" for the exact `_build_signed_headers()` implementation.

Reference: `backend/app/brokers/binance_testnet.py:39-152` for the structural pattern (class skeleton, `__init__`, signing helpers, HTTP helpers, `_check_response`).

- [ ] **Step 1: Write the failing tests for RSA signing**

Create `backend/tests/test_exchange1.py` with tests for `_build_signed_headers()`:

```python
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

        # The payload should have params sorted: a_param before z_param
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

        # Only "symbol" should appear in the sorted params string
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestSigning -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.brokers.exchange1'`

- [ ] **Step 3: Implement Exchange1Broker skeleton with signing and HTTP helpers**

Create `backend/app/brokers/exchange1.py`:

```python
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
    # Stubs (implemented in subsequent tasks)
    # ------------------------------------------------------------------

    async def authenticate(self, credentials: dict) -> bool:
        raise NotImplementedError

    async def verify_connection(self) -> bool:
        raise NotImplementedError

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

    async def get_historical(self, symbol: str, interval: str, start: datetime, end: datetime) -> list[OHLCV]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 4: Run signing tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestSigning -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): add Exchange1Broker skeleton with RSA signing and HTTP helpers"
```

---

### Task 2: Authentication, Connection & Close

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (implement `authenticate`, `verify_connection`, `close`)
- Modify: `backend/tests/test_exchange1.py` (add connection tests)

**Context:** `authenticate()` stores `api_key` and `private_key`, loads RSA key object via `cryptography`, creates `httpx.AsyncClient`, then calls `POST /openapi/v1/token` to validate credentials. `verify_connection()` calls `GET /openapi/v1/balance` as a lightweight authenticated check. `close()` shuts down both HTTP clients and clears secrets from memory. See spec sections "authenticate vs verify_connection" and "HTTP Client Lifecycle".

Reference: `backend/app/brokers/binance_testnet.py:158-200` for the same lifecycle pattern.

- [ ] **Step 1: Write the failing tests for authentication and close**

Append to `backend/tests/test_exchange1.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestConnection -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement authenticate, verify_connection, and close**

Replace the stubs in `backend/app/brokers/exchange1.py`:

```python
async def authenticate(self, credentials: dict) -> bool:
    """Store API key and RSA private key, create HTTP client, validate via token endpoint.

    Expected credentials keys: ``api_key``, ``private_key`` (PEM format).
    Returns True on success, False on auth failure.
    """
    self._api_key = credentials.get("api_key", "")
    self._private_key = credentials.get("private_key", "")

    self._private_key_obj = serialization.load_pem_private_key(
        self._private_key.encode(), password=None,
    )
    self._client = httpx.AsyncClient(timeout=10.0)

    try:
        await self._post("/openapi/v1/token", body={}, signed=True)
        return True
    except RuntimeError:
        return False

async def verify_connection(self) -> bool:
    """Lightweight authenticated check via balance endpoint."""
    try:
        await self._get("/openapi/v1/balance", signed=True)
        return True
    except (RuntimeError, httpx.HTTPError):
        return False

async def close(self) -> None:
    """Shut down HTTP clients and clear secrets from memory."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestConnection -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): implement authenticate, verify_connection, and close"
```

---

### Task 3: Order Placement (BUY & SELL)

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (implement `place_order`)
- Modify: `backend/tests/test_exchange1.py` (add order placement tests)

**Context:** Exchange1 uses separate endpoints for BUY and SELL. BUY goes to `POST /openapi/v1/spot/order/create` with `symbol` (lowercase), `positionType` (market/limit), `quantity`, `quantityUnit` ("cont"). SELL goes to `POST /openapi/v1/spot/order/close` with `symbol`, `positionType`, `closeNum`. LIMIT orders add `price`. Response has `code` (200=success) and `data` (order ID). See spec sections "Order Mapping" and "Response Mapping".

Reference: `backend/app/brokers/binance_testnet.py:206-261` for the place_order pattern.

- [ ] **Step 1: Write the failing tests for order placement**

Append to `backend/tests/test_exchange1.py`:

```python
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
        request_body = route.calls[0].request.content
        import json
        body = json.loads(request_body)
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
        body = __import__("json").loads(route.calls[0].request.content)
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

        body = __import__("json").loads(route.calls[0].request.content)
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

        body = __import__("json").loads(route.calls[0].request.content)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestOrders -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement place_order**

Replace the `place_order` stub in `backend/app/brokers/exchange1.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestOrders -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): implement place_order with BUY/SELL endpoint routing"
```

---

### Task 4: Cancel Order & Get Order Status

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (implement `cancel_order`, `get_order_status`)
- Modify: `backend/tests/test_exchange1.py` (add cancel and status tests)

**Context:** `cancel_order` sends `POST /openapi/v1/spot/order/cancel` with body `{"id": order_id}`. No symbol needed (unlike Binance). `get_order_status` calls `GET /openapi/v1/spot/order/detail?id=order_id` and maps the `state` field via `_STATUS_MAP`. Fill price comes from `tradePrice` or `estimatedPrice`, fill quantity from `doneQuantity`. See spec sections "Cancel Order" and "Order Status Mapping".

- [ ] **Step 1: Write the failing tests for cancel_order and get_order_status**

Append to `backend/tests/test_exchange1.py`:

```python
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
        body = __import__("json").loads(route.calls[0].request.content)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestCancelAndStatus -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement cancel_order and get_order_status**

Replace the stubs in `backend/app/brokers/exchange1.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestCancelAndStatus -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): implement cancel_order and get_order_status"
```

---

### Task 5: Portfolio — Balance, Positions, Holdings

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (implement `_get_balance_data`, `get_balance`, `get_positions`, `get_holdings`)
- Modify: `backend/tests/test_exchange1.py` (add portfolio tests)

**Context:** All three methods share a cached `GET /openapi/v1/balance` call with 2-second TTL (same pattern as Binance adapter's `_get_account_info()`). The balance endpoint returns an accounts array with `{currency, available, hold, total}` objects. USDT balance maps to `AccountBalance`. Non-USDT/USDC non-zero balances become `Position` and `Holding` objects. See spec sections "Balance", "Positions & Holdings", "Account Call Deduplication".

Reference: `backend/app/brokers/binance_testnet.py:315-386` for the exact caching and portfolio pattern.

- [ ] **Step 1: Write the failing tests for portfolio methods**

Append to `backend/tests/test_exchange1.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestPortfolio -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement portfolio methods**

Replace the stubs in `backend/app/brokers/exchange1.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestPortfolio -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): implement portfolio methods with 2s TTL cache"
```

---

### Task 6: Market Data — Quotes & Historical

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (implement `get_quotes`, `get_historical`)
- Modify: `backend/tests/test_exchange1.py` (add market data tests)

**Context:** `get_quotes()` calls `GET /openapi/v1/spot/orderbook?symbol=X` (lowercase) for each symbol, returns best bid/ask and mid price. Empty orderbooks are skipped. `get_historical()` delegates to Binance public REST API `GET https://api.binance.com/api/v3/klines` with the same pagination logic as Binance adapter (max 1000 candles per request, paginate by advancing startTime). A separate `_binance_client` is created lazily. See spec sections "Quotes (Orderbook)" and "Historical Data (Binance Fallback)".

Reference: `backend/app/brokers/binance_testnet.py:392-444` for the exact historical/kline pagination pattern.

- [ ] **Step 1: Write the failing tests for quotes and historical**

Append to `backend/tests/test_exchange1.py`:

```python
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
        # Mid price
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
        from app.brokers.exchange1 import BINANCE_URL
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
        from app.brokers.exchange1 import BINANCE_URL

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestMarketData -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement get_quotes and get_historical**

Replace the stubs in `backend/app/brokers/exchange1.py`:

```python
async def get_quotes(self, symbols: list[str]) -> list[Quote]:
    """Fetch orderbook for each symbol and return best bid/ask with mid price."""
    assert self._client is not None
    quotes: list[Quote] = []
    for symbol in symbols:
        resp = await self._client.get(
            f"{BASE_URL}/openapi/v1/spot/orderbook",
            params={"symbol": symbol.lower()},
        )
        if resp.status_code >= 400:
            continue
        data = resp.json()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py::TestMarketData -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "feat(exchange1): implement get_quotes (orderbook) and get_historical (Binance fallback)"
```

---

### Task 7: Wiring — Factory, __init__, Frontend

**Files:**
- Modify: `backend/app/brokers/factory.py:17-26` — add `"exchange1"` case
- Modify: `backend/app/brokers/__init__.py:1-29` — add `Exchange1Broker` import and export
- Modify: `frontend/app/(dashboard)/brokers/new/page.tsx:11` — fix `secret_key` → `private_key`

**Context:** The factory needs an `"exchange1"` case matching the existing `"binance_testnet"` pattern. The `__init__.py` needs to re-export `Exchange1Broker`. The frontend already has the `exchange1` dropdown and `BROKER_FIELDS` entry but uses `secret_key` instead of `private_key` per the spec (RSA PEM key, not a shared secret).

- [ ] **Step 1: Add exchange1 case to factory.py**

In `backend/app/brokers/factory.py`, add before the `case _:` line:

```python
case "exchange1":
    from app.brokers.exchange1 import Exchange1Broker
    broker = Exchange1Broker()
    authenticated = await broker.authenticate(credentials)
    if not authenticated:
        await broker.close()
        raise RuntimeError("Failed to authenticate with Exchange1")
    return broker
```

- [ ] **Step 2: Add Exchange1Broker to __init__.py**

In `backend/app/brokers/__init__.py`, add the import and export:

```python
from app.brokers.exchange1 import Exchange1Broker
```

And add `"Exchange1Broker"` to `__all__`.

- [ ] **Step 3: Fix frontend credential field name**

In `frontend/app/(dashboard)/brokers/new/page.tsx`, change:

```typescript
exchange1: ["api_key", "secret_key"],
```

to:

```typescript
exchange1: ["api_key", "private_key"],
```

- [ ] **Step 4: Run all Exchange1 tests to ensure nothing broke**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/brokers/factory.py backend/app/brokers/__init__.py frontend/app/\(dashboard\)/brokers/new/page.tsx
git commit -m "feat(exchange1): wire Exchange1Broker into factory, exports, and frontend"
```

---

### Task 8: Full Test Suite Run & Cleanup

**Files:**
- All files from previous tasks

**Context:** Final verification that the complete Exchange1Broker implementation passes all tests and doesn't break existing tests.

- [ ] **Step 1: Run the full Exchange1 test suite**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_exchange1.py -v`
Expected: All tests PASS (signing: 5, connection: 5, orders: 6, cancel/status: 6, portfolio: 5, market data: 4 = ~31 tests)

- [ ] **Step 2: Run existing broker tests to check for regressions**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/test_binance_testnet.py tests/test_broker_factory.py tests/test_brokers.py -v`
Expected: All existing tests PASS

- [ ] **Step 3: Run the full backend test suite**

Run: `cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS
