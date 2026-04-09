# Broker Connection Edit & Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to update broker credentials and reliably delete broker connections from the UI.

**Architecture:** A DB migration adds `ON DELETE CASCADE / SET NULL` to the three FK constraints that block broker deletion. The `PATCH /api/v1/brokers/{id}` endpoint is extended to accept an optional `credentials` dict. On the frontend, a new `UpdateCredentialsModal` component (matching the existing `RenameBrokerModal` pattern) is added to the broker list cards.

**Tech Stack:** FastAPI + SQLAlchemy (Python), Alembic migrations, Next.js 14 + Chakra UI (TypeScript), pytest (backend), Jest + React Testing Library (frontend).

---

## File Map

| File | Action |
|------|--------|
| `backend/app/db/migrations/versions/f2a3b4c5d6e7_broker_connection_cascade_delete.py` | Create — migration adding ondelete clauses |
| `backend/app/db/models.py` | Modify — add `ondelete` to 3 FK column definitions |
| `backend/app/brokers/schemas.py` | Modify — make both fields optional with at-least-one validator |
| `backend/app/brokers/router.py` | Modify — handle optional `credentials` in PATCH endpoint |
| `backend/tests/test_broker_connections.py` | Modify — add cascade tests, credentials update tests |
| `frontend/lib/brokerFields.ts` | Create — shared `BROKER_FIELDS` map |
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Modify — import `BROKER_FIELDS` from shared lib |
| `frontend/components/brokers/UpdateCredentialsModal.tsx` | Create — new modal component |
| `frontend/__tests__/components/UpdateCredentialsModal.test.tsx` | Create — component tests |
| `frontend/app/(dashboard)/brokers/page.tsx` | Modify — key icon button, credentials modal, updated delete message |

---

## Task 1: DB migration — cascade delete for broker connections

**Files:**
- Create: `backend/app/db/migrations/versions/f2a3b4c5d6e7_broker_connection_cascade_delete.py`

- [ ] **Step 1: Write the failing test**

Add these two tests to the end of `backend/tests/test_broker_connections.py`. First update the import block at line ~96 to add `Strategy` and `select`. Replace the existing lines:

```python
from app.db.models import StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState, DeploymentTrade
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from datetime import datetime, UTC
```

with:

```python
from app.db.models import Strategy, StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState, DeploymentTrade
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from datetime import datetime, UTC
```

Then append the two new tests:

```python
@pytest.mark.asyncio
async def test_delete_broker_cascades_deployments(client):
    """Deleting a broker should cascade-delete linked strategy_deployments."""
    tokens = await create_authenticated_user(client, email="cascade_dep@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "Cascade Dep", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="CascadeStrat", code="pass")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, strategy_code_id=code.id, version=1, code="pass"
        )
        session.add(version)
        await session.flush()
        dep = StrategyDeployment(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            strategy_code_id=code.id, strategy_code_version_id=version.id,
            mode="live", status="running", symbol="BTCUSDT",
            exchange="EXCHANGE1", product_type="FUTURES", interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        dep_id = dep.id
        await session.commit()

    resp = await client.delete(f"/api/v1/brokers/{broker_id}", headers=headers)
    assert resp.status_code == 204

    async with async_session_factory() as session:
        result = await session.execute(
            select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
        )
        assert result.scalar_one_or_none() is None, "deployment should be cascade-deleted"


@pytest.mark.asyncio
async def test_delete_broker_nulls_strategy_broker_connection(client):
    """Deleting a broker should SET NULL on Strategy.broker_connection_id."""
    tokens = await create_authenticated_user(client, email="setnull@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "SetNull", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        strat = Strategy(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            name="NullTest", mode="live",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(strat)
        strat_id = strat.id
        await session.commit()

    resp = await client.delete(f"/api/v1/brokers/{broker_id}", headers=headers)
    assert resp.status_code == 204

    async with async_session_factory() as session:
        result = await session.execute(select(Strategy).where(Strategy.id == strat_id))
        strat = result.scalar_one_or_none()
        assert strat is not None, "strategy should still exist"
        assert strat.broker_connection_id is None, "broker_connection_id should be NULL"
```

Also add `select` to the import — it's already imported via `from sqlalchemy import func, select` in conftest but needs to be accessible in test file. Check the top of `test_broker_connections.py`; if it doesn't have `from sqlalchemy import select`, add it.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py::test_delete_broker_cascades_deployments tests/test_broker_connections.py::test_delete_broker_nulls_strategy_broker_connection -v
```

Expected: Both FAIL. `test_delete_broker_cascades_deployments` fails with `AssertionError: deployment should be cascade-deleted` (FK prevents the delete in some setups, or deployment still exists). The exact error depends on whether PostgreSQL raises a FK violation or silently leaves the record.

- [ ] **Step 3: Create the migration file**

Create `backend/app/db/migrations/versions/f2a3b4c5d6e7_broker_connection_cascade_delete.py`:

```python
"""broker_connection_cascade_delete

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # strategies.broker_connection_id → SET NULL on broker delete
    op.drop_constraint(
        "strategies_broker_connection_id_fkey", "strategies", type_="foreignkey"
    )
    op.create_foreign_key(
        "strategies_broker_connection_id_fkey",
        "strategies", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="SET NULL",
    )

    # strategy_deployments.broker_connection_id → CASCADE on broker delete
    op.drop_constraint(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="CASCADE",
    )

    # manual_trades.broker_connection_id → CASCADE on broker delete
    op.drop_constraint(
        "manual_trades_broker_connection_id_fkey", "manual_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "manual_trades_broker_connection_id_fkey",
        "manual_trades", "broker_connections",
        ["broker_connection_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "strategies_broker_connection_id_fkey", "strategies", type_="foreignkey"
    )
    op.create_foreign_key(
        "strategies_broker_connection_id_fkey",
        "strategies", "broker_connections",
        ["broker_connection_id"], ["id"],
    )

    op.drop_constraint(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "strategy_deployments_broker_connection_id_fkey",
        "strategy_deployments", "broker_connections",
        ["broker_connection_id"], ["id"],
    )

    op.drop_constraint(
        "manual_trades_broker_connection_id_fkey", "manual_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "manual_trades_broker_connection_id_fkey",
        "manual_trades", "broker_connections",
        ["broker_connection_id"], ["id"],
    )
```

- [ ] **Step 4: Update the three FK definitions in `backend/app/db/models.py`**

Find `class Strategy` (line ~81) and update its FK:
```python
# Before:
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id"), nullable=True
)

# After (in Strategy class):
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="SET NULL"), nullable=True
)
```

Find `class StrategyDeployment` (line ~303) and update its FK:
```python
# Before:
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id"), nullable=True
)

# After (in StrategyDeployment class):
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="CASCADE"), nullable=True
)
```

Find `class ManualTrade` (line ~443) and update its FK:
```python
# Before:
broker_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broker_connections.id"), nullable=False)

# After (in ManualTrade class):
broker_connection_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="CASCADE"), nullable=False
)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py::test_delete_broker_cascades_deployments tests/test_broker_connections.py::test_delete_broker_nulls_strategy_broker_connection -v
```

Expected: Both PASS.

- [ ] **Step 6: Run the full broker connections test suite to check for regressions**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py -v
```

Expected: All existing tests PASS.

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/db/migrations/versions/f2a3b4c5d6e7_broker_connection_cascade_delete.py \
        app/db/models.py \
        tests/test_broker_connections.py
git commit -m "feat: cascade delete strategy_deployments and manual_trades on broker deletion"
```

---

## Task 2: Backend — extend PATCH endpoint to update credentials

**Files:**
- Modify: `backend/app/brokers/schemas.py`
- Modify: `backend/app/brokers/router.py`
- Modify: `backend/tests/test_broker_connections.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `backend/tests/test_broker_connections.py`:

```python
# ---------------------------------------------------------------------------
# Schema unit tests — UpdateBrokerConnectionRequest credentials support
# ---------------------------------------------------------------------------

def test_update_schema_credentials_only_is_valid():
    req = UpdateBrokerConnectionRequest(credentials={"api_key": "k", "private_key": "p"})
    assert req.credentials == {"api_key": "k", "private_key": "p"}
    assert req.label is None


def test_update_schema_both_fields_is_valid():
    req = UpdateBrokerConnectionRequest(label="MyBroker", credentials={"api_key": "k"})
    assert req.label == "MyBroker"
    assert req.credentials == {"api_key": "k"}


# Note: `test_update_schema_requires_label` (already in the file) still passes
# because calling UpdateBrokerConnectionRequest() with no args triggers
# the at_least_one_field validator → same ValidationError.

# ---------------------------------------------------------------------------
# API tests — PATCH credentials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_broker_connection_updates_credentials(client):
    """PATCH with credentials should re-encrypt and store new credentials."""
    tokens = await create_authenticated_user(client, email="creds_update@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Creds Test",
            "credentials": {"api_key": "old-key", "private_key": "old-private"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"credentials": {"api_key": "new-key", "private_key": "new-private"}},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == conn_id
    assert body["label"] == "Creds Test"  # label unchanged
    assert "credentials" not in body       # credentials never returned


@pytest.mark.asyncio
async def test_patch_broker_connection_label_and_credentials_together(client):
    """PATCH with both label and credentials updates both."""
    tokens = await create_authenticated_user(client, email="both_update@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Original",
            "credentials": {"api_key": "old", "private_key": "old-p"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "Updated", "credentials": {"api_key": "new", "private_key": "new-p"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated"


@pytest.mark.asyncio
async def test_patch_broker_connection_empty_body_returns_422(client):
    """PATCH with no fields should return 422."""
    tokens = await create_authenticated_user(client, email="empty_patch@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "zerodha", "label": "E", "credentials": {"api_key": "k", "api_secret": "s"}},
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={},
        headers=headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py::test_update_schema_credentials_only_is_valid tests/test_broker_connections.py::test_patch_broker_connection_updates_credentials -v
```

Expected: FAIL — `UpdateBrokerConnectionRequest` doesn't accept `credentials` yet.

- [ ] **Step 3: Update `backend/app/brokers/schemas.py`**

Replace the entire file content:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


def validate_label(v: str) -> str:
    """Trim, require non-empty after trim, cap at 40 chars."""
    if not isinstance(v, str):
        raise ValueError("label must be a string")
    stripped = v.strip()
    if not stripped:
        raise ValueError("label cannot be blank")
    if len(stripped) > 40:
        raise ValueError("label cannot exceed 40 characters")
    return stripped


class CreateBrokerConnectionRequest(BaseModel):
    broker_type: str
    label: str
    credentials: dict

    _validate_label = field_validator("label")(validate_label)


class UpdateBrokerConnectionRequest(BaseModel):
    label: str | None = None
    credentials: dict | None = None

    @field_validator("label", mode="before")
    @classmethod
    def validate_label_if_provided(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_label(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateBrokerConnectionRequest":
        if self.label is None and self.credentials is None:
            raise ValueError("at least one of label or credentials must be provided")
        return self


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    label: str
    is_active: bool
    connected_at: datetime
    # NO credentials in response


class BrokerStatsResponse(BaseModel):
    active_deployments: int
    total_realized_pnl: float
    win_rate: float
    total_trades: int


class BrokerPositionResponse(BaseModel):
    deployment_id: str
    deployment_name: str
    symbol: str
    side: str           # "LONG" or "SHORT"
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float


class BrokerBalanceResponse(BaseModel):
    available: float
    total: float


class BrokerOrderResponse(BaseModel):
    order_id: str
    deployment_id: str
    deployment_name: str
    symbol: str
    action: str
    quantity: float
    order_type: str
    price: float | None
    created_at: str | None
```

- [ ] **Step 4: Update `backend/app/brokers/router.py` — the PATCH endpoint**

Replace the `update_broker_connection` function (lines 107–145) with:

```python
@router.patch("/{connection_id}", response_model=BrokerConnectionResponse)
async def update_broker_connection(
    connection_id: uuid.UUID,
    body: UpdateBrokerConnectionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )

    if body.label is not None:
        conn.label = body.label
    if body.credentials is not None:
        conn.credentials = encrypt_credentials(tenant_id, body.credentials)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A broker connection with this label already exists",
        )
    await session.refresh(conn)

    return BrokerConnectionResponse(
        id=conn.id,
        broker_type=conn.broker_type,
        label=conn.label,
        is_active=conn.is_active,
        connected_at=conn.connected_at,
    )
```

- [ ] **Step 5: Run the new tests to verify they pass**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py::test_update_schema_credentials_only_is_valid tests/test_broker_connections.py::test_update_schema_both_fields_is_valid tests/test_broker_connections.py::test_update_schema_neither_field_raises tests/test_broker_connections.py::test_patch_broker_connection_updates_credentials tests/test_broker_connections.py::test_patch_broker_connection_label_and_credentials_together tests/test_broker_connections.py::test_patch_broker_connection_empty_body_returns_422 -v
```

Expected: All 6 PASS.

- [ ] **Step 6: Run the full broker connections test suite**

```bash
cd backend
.venv/bin/pytest tests/test_broker_connections.py -v
```

Expected: All tests PASS. Note: `test_update_schema_requires_label` still passes because calling `UpdateBrokerConnectionRequest()` with no args triggers the `at_least_one_field` validator (same behaviour, different validator).

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/brokers/schemas.py app/brokers/router.py tests/test_broker_connections.py
git commit -m "feat: extend PATCH /brokers endpoint to accept optional credentials update"
```

---

## Task 3: Frontend — extract BROKER_FIELDS to shared lib

**Files:**
- Create: `frontend/lib/brokerFields.ts`
- Modify: `frontend/app/(dashboard)/brokers/new/page.tsx`

- [ ] **Step 1: Create `frontend/lib/brokerFields.ts`**

```typescript
/** Credential field names required per broker type. */
export const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "private_key"],
  binance_testnet: ["api_key", "api_secret"],
};
```

- [ ] **Step 2: Update `frontend/app/(dashboard)/brokers/new/page.tsx`**

Replace the inline `BROKER_FIELDS` constant (lines 10–14) with an import:

```typescript
// Remove this block:
const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "private_key"],
  binance_testnet: ["api_key", "api_secret"],
};

// Add this import at the top of the file (with the other imports):
import { BROKER_FIELDS } from "@/lib/brokerFields";
```

- [ ] **Step 3: Run the frontend tests to verify nothing broke**

```bash
cd frontend
npx jest --testPathPattern="brokers" --no-coverage
```

Expected: All existing broker-related tests PASS.

- [ ] **Step 4: Commit**

```bash
cd frontend
git add lib/brokerFields.ts app/\(dashboard\)/brokers/new/page.tsx
git commit -m "refactor: extract BROKER_FIELDS to shared lib"
```

---

## Task 4: Frontend — UpdateCredentialsModal component

**Files:**
- Create: `frontend/components/brokers/UpdateCredentialsModal.tsx`
- Create: `frontend/__tests__/components/UpdateCredentialsModal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/components/UpdateCredentialsModal.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { UpdateCredentialsModal } from "@/components/brokers/UpdateCredentialsModal";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

function setup(overrides: Partial<React.ComponentProps<typeof UpdateCredentialsModal>> = {}) {
  const onClose = jest.fn();
  const onUpdated = jest.fn();
  render(
    <ChakraProvider>
      <UpdateCredentialsModal
        isOpen
        onClose={onClose}
        onUpdated={onUpdated}
        connectionId="conn-123"
        brokerType="exchange1"
        {...overrides}
      />
    </ChakraProvider>,
  );
  return { onClose, onUpdated };
}

describe("UpdateCredentialsModal", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("renders credential fields for the broker type", () => {
    setup();
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/private key/i)).toBeInTheDocument();
  });

  it("Update button is disabled when fields are empty", () => {
    setup();
    expect(screen.getByRole("button", { name: /update/i })).toBeDisabled();
  });

  it("calls PATCH with credentials and invokes onUpdated on success", async () => {
    mockApiClient.mockResolvedValueOnce({});
    const { onUpdated } = setup();

    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "new-key" } });
    fireEvent.change(screen.getByLabelText(/private key/i), { target: { value: "new-private" } });
    fireEvent.click(screen.getByRole("button", { name: /update/i }));

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1));
    expect(mockApiClient).toHaveBeenCalledWith(
      "/api/v1/brokers/conn-123",
      expect.objectContaining({
        method: "PATCH",
        body: { credentials: { api_key: "new-key", private_key: "new-private" } },
      }),
    );
    await waitFor(() => expect(onUpdated).toHaveBeenCalledTimes(1));
  });

  it("shows error message and stays open on failure", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Server error"));
    const { onClose } = setup();

    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "k" } });
    fireEvent.change(screen.getByLabelText(/private key/i), { target: { value: "p" } });
    fireEvent.click(screen.getByRole("button", { name: /update/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to update credentials/i)).toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders zerodha fields when brokerType is zerodha", () => {
    setup({ brokerType: "zerodha" });
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api secret/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/user id/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend
npx jest __tests__/components/UpdateCredentialsModal.test.tsx --no-coverage
```

Expected: FAIL — `UpdateCredentialsModal` module not found.

- [ ] **Step 3: Create `frontend/components/brokers/UpdateCredentialsModal.tsx`**

```typescript
"use client";
import {
  Button,
  FormControl,
  FormLabel,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { BROKER_FIELDS } from "@/lib/brokerFields";

export interface UpdateCredentialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
  connectionId: string;
  brokerType: string;
}

export function UpdateCredentialsModal({
  isOpen,
  onClose,
  onUpdated,
  connectionId,
  brokerType,
}: UpdateCredentialsModalProps) {
  const fields = BROKER_FIELDS[brokerType] ?? [];
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setCredentials({});
      setError(null);
      setSaving(false);
    }
  }, [isOpen]);

  const allFilled =
    fields.length > 0 && fields.every((f) => (credentials[f] ?? "").trim().length > 0);

  const handleSave = async () => {
    if (!allFilled) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/v1/brokers/${connectionId}`, {
        method: "PATCH",
        body: { credentials },
      });
      onUpdated();
      onClose();
    } catch {
      setError("Failed to update credentials");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Update credentials</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={3} align="stretch">
            {fields.map((field) => (
              <FormControl key={field} isRequired>
                <FormLabel>
                  {field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </FormLabel>
                <Input
                  type="password"
                  value={credentials[field] ?? ""}
                  onChange={(e) => {
                    setCredentials((prev) => ({ ...prev, [field]: e.target.value }));
                    setError(null);
                  }}
                  placeholder={`Enter new ${field}`}
                />
              </FormControl>
            ))}
            {error && (
              <Text color="red.400" fontSize="sm">
                {error}
              </Text>
            )}
          </VStack>
        </ModalBody>
        <ModalFooter gap={2}>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSave}
            isLoading={saving}
            isDisabled={!allFilled}
          >
            Update
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend
npx jest __tests__/components/UpdateCredentialsModal.test.tsx --no-coverage
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add components/brokers/UpdateCredentialsModal.tsx \
        __tests__/components/UpdateCredentialsModal.test.tsx
git commit -m "feat: add UpdateCredentialsModal component"
```

---

## Task 5: Frontend — wire broker list page

**Files:**
- Modify: `frontend/app/(dashboard)/brokers/page.tsx`

- [ ] **Step 1: Replace `frontend/app/(dashboard)/brokers/page.tsx`**

Replace the entire file:

```typescript
"use client";
import {
  Box,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardHeader,
  Flex,
  Heading,
  IconButton,
  SimpleGrid,
  Text,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { MdEdit, MdKey } from "react-icons/md";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EmptyState } from "@/components/shared/EmptyState";
import { RenameBrokerModal } from "@/components/brokers/RenameBrokerModal";
import { UpdateCredentialsModal } from "@/components/brokers/UpdateCredentialsModal";
import { useBrokers } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function BrokersPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers, isLoading, mutate } = useBrokers();
  const deleteDisclosure = useDisclosure();
  const renameDisclosure = useDisclosure();
  const credentialsDisclosure = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ id: string; label: string } | null>(null);
  const [credentialsTarget, setCredentialsTarget] = useState<{
    id: string;
    brokerType: string;
  } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient(`/api/v1/brokers/${deleteTarget}`, { method: "DELETE" });
      toast({ title: "Broker deleted", status: "success", duration: 3000 });
      mutate();
    } catch {
      toast({ title: "Failed to delete broker", status: "error", duration: 3000 });
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
      deleteDisclosure.onClose();
    }
  };

  const list = brokers ?? [];

  if (!isLoading && list.length === 0) {
    return (
      <Box>
        <Flex justify="space-between" align="center" mb={6}>
          <Heading size="lg">Brokers</Heading>
          <Button size="sm" colorScheme="blue" onClick={() => router.push("/brokers/new")}>
            Add Broker
          </Button>
        </Flex>
        <EmptyState
          title="No brokers connected"
          description="Connect a broker to start trading."
          actionLabel="Add Broker"
          onAction={() => router.push("/brokers/new")}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Brokers</Heading>
        <Button size="sm" colorScheme="blue" onClick={() => router.push("/brokers/new")}>
          Add Broker
        </Button>
      </Flex>

      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        {list.map((broker) => (
          <Link key={broker.id} href={`/brokers/${broker.id}`} style={{ textDecoration: "none" }}>
            <Card
              _hover={{ borderColor: "blue.400", cursor: "pointer" }}
              transition="border-color 0.15s"
            >
              <CardHeader pb={2}>
                <Flex justify="space-between" align="start">
                  <Box>
                    <Text fontWeight="bold" fontSize="lg">
                      {broker.label}
                    </Text>
                    <Text fontSize="xs" color="gray.500" textTransform="uppercase">
                      {broker.broker_type}
                    </Text>
                  </Box>
                  <StatusBadge
                    variant={broker.is_active ? "success" : "neutral"}
                    text={broker.is_active ? "Active" : "Inactive"}
                  />
                </Flex>
              </CardHeader>
              <CardBody py={2}>
                <Text fontSize="sm" color="gray.500">
                  Connected: {formatDate(broker.connected_at)}
                </Text>
              </CardBody>
              <CardFooter pt={2} gap={2}>
                <IconButton
                  aria-label="Rename broker"
                  icon={<MdEdit />}
                  size="xs"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    setRenameTarget({ id: broker.id, label: broker.label });
                    renameDisclosure.onOpen();
                  }}
                />
                <IconButton
                  aria-label="Update credentials"
                  icon={<MdKey />}
                  size="xs"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    setCredentialsTarget({ id: broker.id, brokerType: broker.broker_type });
                    credentialsDisclosure.onOpen();
                  }}
                />
                <Button
                  size="xs"
                  colorScheme="red"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    setDeleteTarget(broker.id);
                    deleteDisclosure.onOpen();
                  }}
                >
                  Delete
                </Button>
              </CardFooter>
            </Card>
          </Link>
        ))}
      </SimpleGrid>

      <ConfirmModal
        isOpen={deleteDisclosure.isOpen}
        onClose={() => {
          setDeleteTarget(null);
          deleteDisclosure.onClose();
        }}
        onConfirm={handleDelete}
        title="Delete Broker"
        message="This will permanently delete the broker connection and all linked deployments and trade history. This action cannot be undone."
        confirmLabel="Delete"
        isLoading={deleting}
      />

      {renameTarget && (
        <RenameBrokerModal
          isOpen={renameDisclosure.isOpen}
          onClose={() => {
            setRenameTarget(null);
            renameDisclosure.onClose();
          }}
          onRenamed={() => {
            mutate();
            toast({ title: "Broker renamed", status: "success", duration: 3000 });
          }}
          connectionId={renameTarget.id}
          currentLabel={renameTarget.label}
        />
      )}

      {credentialsTarget && (
        <UpdateCredentialsModal
          isOpen={credentialsDisclosure.isOpen}
          onClose={() => {
            setCredentialsTarget(null);
            credentialsDisclosure.onClose();
          }}
          onUpdated={() => {
            toast({ title: "Credentials updated", status: "success", duration: 3000 });
          }}
          connectionId={credentialsTarget.id}
          brokerType={credentialsTarget.brokerType}
        />
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npx jest --no-coverage
```

Expected: All tests PASS (including pre-existing `RenameBrokerModal` and new `UpdateCredentialsModal` tests).

- [ ] **Step 3: Commit**

```bash
cd frontend
git add app/\(dashboard\)/brokers/page.tsx
git commit -m "feat: add update credentials button and fix delete warning on broker cards"
```

---

## Final step: Run migrations on the production server and deploy

- [ ] **Run migration on server**

```bash
# From worktree root
SERVER_PASS=$(grep '^password:' contabo-server.txt | awk '{print $2}')
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/backend && .venv/bin/alembic upgrade head"'
```

Expected output includes: `Running upgrade e1f2a3b4c5d6 -> f2a3b4c5d6e7, broker_connection_cascade_delete`

- [ ] **Deploy**

Run `/deploy` to push all changes to production.
