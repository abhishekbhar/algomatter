# Broker Connection Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-chosen `label` to broker connections so multiple connections to the same broker (e.g. two `exchange1` keys) can be distinguished everywhere the UI renders a connection.

**Architecture:** One new `VARCHAR(40) NOT NULL` column on `broker_connections` with a composite unique index on `(tenant_id, label)`. One shared `validate_label` helper enforces trim + non-empty + max-length at the Pydantic layer. Router catches `IntegrityError` on create/rename and re-raises as HTTP 409. Frontend surfaces the label in 4 existing display points (list card, detail heading, and 3 dropdowns) and gains a rename modal.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy (async), Alembic, PostgreSQL, Next.js 15 + Chakra UI, Jest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-04-08-broker-connection-label-design.md`

**Repo note:** The tracked git repo is rooted at `algomatter/`. All paths in this plan are **relative to `algomatter/`** unless otherwise stated.

---

## File Structure

### Backend (Python)

| Path | Responsibility | Change |
|---|---|---|
| `backend/app/db/migrations/versions/c8e1d2f3a4b5_broker_connection_label.py` | Alembic migration: add column, backfill existing rows, set NOT NULL, create composite unique index. | **create** |
| `backend/app/db/models.py` | SQLAlchemy `BrokerConnection` model — add `label` field. | **modify** |
| `backend/app/brokers/schemas.py` | Pydantic request/response models; add `validate_label` helper, update `CreateBrokerConnectionRequest`, add `UpdateBrokerConnectionRequest`, add `label` to `BrokerConnectionResponse`. | **modify** |
| `backend/app/brokers/router.py` | Persist label on POST, handle `IntegrityError` → 409, new `PATCH /api/v1/brokers/{id}`. | **modify** |
| `backend/tests/test_broker_connections.py` | Add label to 14 existing POST fixtures; add label-specific POST tests and new PATCH tests. | **modify** |

### Frontend (TypeScript + React)

| Path | Responsibility | Change |
|---|---|---|
| `frontend/lib/api/types.ts` | `BrokerConnection` TS interface — add `label: string`. | **modify** |
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Connect form — add required "Label" input with client validation. | **modify** |
| `frontend/components/brokers/RenameBrokerModal.tsx` | New modal component: loads current label, PATCHes new label, handles 409 inline. | **create** |
| `frontend/app/(dashboard)/brokers/page.tsx` | Card title = `label` (bold), `broker_type` as small uppercase subtitle, new edit icon that opens `RenameBrokerModal`. | **modify** |
| `frontend/app/(dashboard)/brokers/[id]/page.tsx` | Heading = `label`, `broker_type` as subtitle. | **modify** |
| `frontend/app/(dashboard)/strategies/new/page.tsx` | Broker dropdown display → `{label} — {broker_type}{inactive? " (Inactive)" : ""}`. | **modify** |
| `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx` | Same dropdown change as above. | **modify** |
| `frontend/components/deployments/PromoteModal.tsx` | Replace `id.slice(0, 8)` hack with `{label} — {broker_type}`. | **modify** |
| `frontend/__tests__/pages/brokers.test.tsx` | Update existing fixtures to include `label`; add tests for card title/subtitle, edit button, rename happy path, rename 409 error display. | **modify** |
| `frontend/__tests__/pages/broker-detail.test.tsx` | Update fixture to include `label`; assert heading renders label. | **modify** |
| `frontend/__tests__/components/RenameBrokerModal.test.tsx` | Component tests for the new modal. | **create** |

### Deployment

- Run Alembic `upgrade head` against the prod DB (via existing deploy flow).
- Redeploy `algomatter-api`, `algomatter-worker`, `algomatter-strategy-runner`, `algomatter-frontend`.

---

## Task 1: Backend — Label on the create path

**Goal:** After this task, the backend enforces a required, trimmed, unique, ≤40-char `label` on every broker connection, the DB has the column + index, and the existing test suite is green.

**Files:**
- Create: `backend/app/db/migrations/versions/c8e1d2f3a4b5_broker_connection_label.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/brokers/schemas.py`
- Modify: `backend/app/brokers/router.py:48-71` (POST `create_broker_connection`) and `:74-92` (GET `list_broker_connections`)
- Modify: `backend/tests/test_broker_connections.py`

### Steps

- [ ] **Step 1.1: Create the Alembic migration file**

Create `backend/app/db/migrations/versions/c8e1d2f3a4b5_broker_connection_label.py` with the following contents:

```python
"""broker_connection_label

Revision ID: c8e1d2f3a4b5
Revises: b7d4e9f1a2c3
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e1d2f3a4b5'
down_revision: Union[str, None] = 'b7d4e9f1a2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column as nullable so backfill can run
    op.add_column(
        'broker_connections',
        sa.Column('label', sa.String(length=40), nullable=True),
    )

    # 2. Backfill every existing row with a unique placeholder:
    #    "<broker_type> #<first 8 chars of id>"
    op.execute(
        """
        UPDATE broker_connections
        SET label = broker_type || ' #' || substr(id::text, 1, 8)
        WHERE label IS NULL
        """
    )

    # 3. Flip to NOT NULL now that every row has a value
    op.alter_column('broker_connections', 'label', nullable=False)

    # 4. Composite unique index: a label is unique within a tenant
    op.create_index(
        'ix_broker_connections_tenant_label',
        'broker_connections',
        ['tenant_id', 'label'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_broker_connections_tenant_label', table_name='broker_connections')
    op.drop_column('broker_connections', 'label')
```

- [ ] **Step 1.2: Apply the migration to the test database and verify**

Run:
```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```
Expected: Ends with `Running upgrade b7d4e9f1a2c3 -> c8e1d2f3a4b5, broker_connection_label` and no error.

Then verify the index exists:
```bash
psql "$DATABASE_URL" -c "\d broker_connections"
```
Expected: `label` column present, `ix_broker_connections_tenant_label` composite unique index listed.

(If running inside the Nix dev shell and the test DB isn't up, start it with `docker compose -f docker-compose.infra.yml up -d` from the repo root.)

- [ ] **Step 1.3: Update the ORM model**

Edit `backend/app/db/models.py`. Find the `BrokerConnection` class and add a `label` field next to `is_active`:

```python
class BrokerConnection(Base):
    __tablename__ = "broker_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    broker_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    credentials: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 1.4: Write failing Pydantic tests for `validate_label`**

Open `backend/tests/test_broker_connections.py`. At the top of the file, add:

```python
import pytest
from pydantic import ValidationError
from app.brokers.schemas import (
    CreateBrokerConnectionRequest,
    UpdateBrokerConnectionRequest,
)
```

Then append the following test block at the end of the file:

```python
# -----------------------------------------------------------------------------
# validate_label — schema-layer unit tests
# -----------------------------------------------------------------------------

def _valid_creds():
    return {"api_key": "k", "api_secret": "s"}


def test_create_schema_requires_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(broker_type="zerodha", credentials=_valid_creds())


def test_create_schema_rejects_blank_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(
            broker_type="zerodha", label="   ", credentials=_valid_creds()
        )


def test_create_schema_rejects_too_long_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(
            broker_type="zerodha", label="x" * 41, credentials=_valid_creds()
        )


def test_create_schema_trims_whitespace():
    req = CreateBrokerConnectionRequest(
        broker_type="zerodha", label="  Main  ", credentials=_valid_creds()
    )
    assert req.label == "Main"


def test_update_schema_requires_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest()  # type: ignore[call-arg]


def test_update_schema_rejects_blank_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest(label="")


def test_update_schema_rejects_too_long_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest(label="y" * 41)


def test_update_schema_trims_whitespace():
    req = UpdateBrokerConnectionRequest(label="  My Account  ")
    assert req.label == "My Account"
```

- [ ] **Step 1.5: Run the new schema tests and verify they fail**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_broker_connections.py -v -k "schema"
```
Expected: `ImportError` or `AttributeError` on `UpdateBrokerConnectionRequest` (doesn't exist yet) — all schema tests fail.

- [ ] **Step 1.6: Implement the schema changes**

Replace the entirety of `backend/app/brokers/schemas.py` with:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


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
    label: str

    _validate_label = field_validator("label")(validate_label)


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

- [ ] **Step 1.7: Run the schema tests and verify they pass**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_broker_connections.py -v -k "schema"
```
Expected: all 8 schema tests pass.

- [ ] **Step 1.8: Update the POST `create_broker_connection` router to persist the label and handle 409**

Edit `backend/app/brokers/router.py`. Replace the existing `create_broker_connection` function (lines ~43-71) with:

```python
from sqlalchemy.exc import IntegrityError


@router.post(
    "",
    response_model=BrokerConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_connection(
    body: CreateBrokerConnectionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    encrypted = encrypt_credentials(tenant_id, body.credentials)

    conn = BrokerConnection(
        tenant_id=tenant_id,
        broker_type=body.broker_type,
        label=body.label,
        credentials=encrypted,
        is_active=True,
    )
    session.add(conn)
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

The `from sqlalchemy.exc import IntegrityError` should go at the top of the file with the other `sqlalchemy` imports. If the file already imports from `sqlalchemy.exc`, add to that line; otherwise add a new import line after the other `sqlalchemy` imports near the top.

- [ ] **Step 1.9: Update the GET `list_broker_connections` router to return `label`**

In the same file, replace the existing `list_broker_connections` function (lines ~74-92) with:

```python
@router.get("", response_model=list[BrokerConnectionResponse])
async def list_broker_connections(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(BrokerConnection.tenant_id == tenant_id)
    )
    connections = result.scalars().all()
    return [
        BrokerConnectionResponse(
            id=c.id,
            broker_type=c.broker_type,
            label=c.label,
            is_active=c.is_active,
            connected_at=c.connected_at,
        )
        for c in connections
    ]
```

- [ ] **Step 1.10: Update all 14 existing POST fixtures in `test_broker_connections.py` to send a label**

In `backend/tests/test_broker_connections.py`, every POST to `/api/v1/brokers` currently looks like either:

```python
json={
    "broker_type": "zerodha",
    "credentials": {"api_key": "xxx", "api_secret": "yyy"},
},
```

or

```python
json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
```

Add `"label"` to each one with a **unique value per test function** (so tests that create multiple connections in the same tenant don't collide). Use the test function name (or a short variant) as the label, suffixed with `" A"`, `" B"` if the same test creates multiple. Examples:

In `test_create_broker_connection`:
```python
json={
    "broker_type": "zerodha",
    "label": "Create Test",
    "credentials": {"api_key": "xxx", "api_secret": "yyy"},
},
```

In `test_list_broker_connections`:
```python
json={
    "broker_type": "zerodha",
    "label": "List Test",
    "credentials": {"api_key": "xxx", "api_secret": "yyy"},
},
```

In `test_delete_broker_connection`:
```python
json={
    "broker_type": "zerodha",
    "label": "Delete Test",
    "credentials": {"api_key": "xxx", "api_secret": "yyy"},
},
```

In `test_rls_isolation_broker_connections` — user A's POST gets `"label": "RLS A"`.

In `test_get_broker_stats_with_data` and the other `stats`/`positions`/`orders`/`trades` tests (lines ~99, 156, 206, 256, 307, 334, 358, 381, 407) — each gets a unique label like `"Stats Test"`, `"Positions Test"`, `"Orders Test"`, `"Trades Test"`, etc. If any test has multiple POSTs, append `" A"`/`" B"`.

- [ ] **Step 1.11: Extend the existing `test_create_broker_connection` to assert the label is echoed back**

Replace the assertion block in `test_create_broker_connection` (around line 17-22) with:

```python
    assert resp.status_code == 201
    data = resp.json()
    assert data["broker_type"] == "zerodha"
    assert data["label"] == "Create Test"
    assert "credentials" not in data  # credentials must not be in response
    assert "id" in data
    assert data["is_active"] is True
```

- [ ] **Step 1.12: Add new POST-endpoint tests for label behavior**

Append the following tests to `backend/tests/test_broker_connections.py` (after the existing CRUD tests, before the schema unit tests you added in Step 1.4):

```python
@pytest.mark.asyncio
async def test_create_broker_connection_returns_422_without_label(client):
    tokens = await create_authenticated_user(client, email="nolabel@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_broker_connection_trims_label(client):
    tokens = await create_authenticated_user(client, email="trim@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "   Padded   ",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["label"] == "Padded"


@pytest.mark.asyncio
async def test_create_broker_connection_duplicate_label_returns_409(client):
    tokens = await create_authenticated_user(client, email="dup@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = {
        "broker_type": "zerodha",
        "label": "Duplicate",
        "credentials": {"api_key": "xxx", "api_secret": "yyy"},
    }
    first = await client.post("/api/v1/brokers", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/brokers", json=payload, headers=headers)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_broker_connection_same_label_different_tenants_ok(client):
    tokens_a = await create_authenticated_user(client, email="tenant_a@test.com")
    tokens_b = await create_authenticated_user(client, email="tenant_b@test.com")
    payload = {
        "broker_type": "zerodha",
        "label": "Shared Name",
        "credentials": {"api_key": "xxx", "api_secret": "yyy"},
    }
    resp_a = await client.post(
        "/api/v1/brokers",
        json=payload,
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    resp_b = await client.post(
        "/api/v1/brokers",
        json=payload,
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


@pytest.mark.asyncio
async def test_list_broker_connections_includes_label(client):
    tokens = await create_authenticated_user(client, email="listlabel@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Main Account",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/brokers", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["label"] == "Main Account"
```

- [ ] **Step 1.13: Run the full broker connections test file and verify everything passes**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_broker_connections.py -v
```
Expected: all tests pass — the 4 original CRUD tests (with updated fixtures), the 10 existing stats/positions/orders/trades tests (with updated fixtures), the 5 new label POST tests, and the 8 new schema unit tests.

If any test that was previously passing now fails, the likely cause is a missing `"label"` in a fixture — re-check Step 1.10.

- [ ] **Step 1.14: Run the full backend test suite to make sure nothing else regressed**

Run:
```bash
cd backend && source .venv/bin/activate && pytest
```
Expected: the whole suite passes. Any failure in an unrelated file likely means another test creates broker connections — search for `/api/v1/brokers` and `BrokerConnection(` in `tests/` and update accordingly.

- [ ] **Step 1.15: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add backend/app/db/migrations/versions/c8e1d2f3a4b5_broker_connection_label.py \
        backend/app/db/models.py \
        backend/app/brokers/schemas.py \
        backend/app/brokers/router.py \
        backend/tests/test_broker_connections.py
git commit -m "$(cat <<'EOF'
feat(brokers): add required label column to broker connections

Adds a user-chosen label (max 40 chars, trimmed, unique per tenant) to
broker_connections so multiple accounts on the same broker can be
distinguished in the UI. Existing rows are backfilled with
"<broker_type> #<first 8 chars of id>". Duplicate labels return 409.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend — PATCH rename endpoint

**Goal:** A new `PATCH /api/v1/brokers/{id}` endpoint lets users rename an existing connection. Duplicate labels return 409, missing or cross-tenant returns 404, and renaming to the current label is a no-op 200.

**Files:**
- Modify: `backend/app/brokers/router.py` (add new PATCH handler)
- Modify: `backend/tests/test_broker_connections.py` (add PATCH tests)

### Steps

- [ ] **Step 2.1: Write the failing PATCH tests**

Append to `backend/tests/test_broker_connections.py`:

```python
@pytest.mark.asyncio
async def test_patch_broker_connection_renames_label(client):
    tokens = await create_authenticated_user(client, email="rename@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Original",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "Renamed"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == conn_id
    assert body["label"] == "Renamed"
    assert "credentials" not in body


@pytest.mark.asyncio
async def test_patch_broker_connection_trims_label(client):
    tokens = await create_authenticated_user(client, email="rename_trim@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Pre-trim",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "   Post-trim   "},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Post-trim"


@pytest.mark.asyncio
async def test_patch_broker_connection_rejects_blank_label(client):
    tokens = await create_authenticated_user(client, email="rename_blank@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Blank Source",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "   "},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_broker_connection_rename_to_existing_returns_409(client):
    tokens = await create_authenticated_user(client, email="rename_conflict@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Taken",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    other = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Other",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    other_id = other.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{other_id}",
        json={"label": "Taken"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_broker_connection_rename_to_own_current_label_is_ok(client):
    tokens = await create_authenticated_user(client, email="rename_self@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Self",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "Self"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Self"


@pytest.mark.asyncio
async def test_patch_broker_connection_not_found_returns_404(client):
    tokens = await create_authenticated_user(client, email="rename_missing@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.patch(
        "/api/v1/brokers/00000000-0000-0000-0000-000000000000",
        json={"label": "Nope"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_broker_connection_other_tenant_returns_404(client):
    tokens_a = await create_authenticated_user(client, email="cross_a@test.com")
    tokens_b = await create_authenticated_user(client, email="cross_b@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    create_a = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "A's broker",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers_a,
    )
    a_id = create_a.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{a_id}",
        json={"label": "Hijacked"},
        headers=headers_b,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2.2: Run the new tests and verify they fail**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_broker_connections.py -v -k "patch_broker"
```
Expected: all 7 new tests fail with HTTP 405 Method Not Allowed (endpoint doesn't exist yet).

- [ ] **Step 2.3: Implement the PATCH endpoint**

Edit `backend/app/brokers/router.py`. Add the `UpdateBrokerConnectionRequest` import at the top (extend the existing `from app.brokers.schemas import (...)` import block):

```python
from app.brokers.schemas import (
    BrokerBalanceResponse,
    BrokerConnectionResponse,
    BrokerOrderResponse,
    BrokerPositionResponse,
    BrokerStatsResponse,
    CreateBrokerConnectionRequest,
    UpdateBrokerConnectionRequest,
)
```

Then add the new PATCH handler **immediately after** `list_broker_connections` and **before** `delete_broker_connection`:

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

    conn.label = body.label
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

- [ ] **Step 2.4: Run the PATCH tests and verify they pass**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_broker_connections.py -v -k "patch_broker"
```
Expected: all 7 PATCH tests pass.

- [ ] **Step 2.5: Run the full backend suite**

Run:
```bash
cd backend && source .venv/bin/activate && pytest
```
Expected: entire suite passes.

- [ ] **Step 2.6: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add backend/app/brokers/router.py backend/tests/test_broker_connections.py
git commit -m "$(cat <<'EOF'
feat(brokers): add PATCH rename endpoint for broker connections

New PATCH /api/v1/brokers/{id} endpoint lets users rename a connection.
Tenant-scoped (404 cross-tenant), duplicate labels return 409, renaming
to the current label is a valid no-op.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend — `BrokerConnection` TypeScript type

**Goal:** The `BrokerConnection` TS interface knows about `label`.

**Files:**
- Modify: `frontend/lib/api/types.ts:56-61`

### Steps

- [ ] **Step 3.1: Add `label` to the `BrokerConnection` interface**

Edit `frontend/lib/api/types.ts`. Find the `BrokerConnection` interface and add a `label` field after `broker_type`:

```ts
export interface BrokerConnection {
  id: string;
  broker_type: string;
  label: string;
  is_active: boolean;
  connected_at: string;
}
```

- [ ] **Step 3.2: Run `tsc --noEmit` to catch any type errors immediately**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: the compiler will flag **several** places where a `BrokerConnection` fixture or object is constructed without `label` — primarily in the test files (`__tests__/pages/brokers.test.tsx`, `__tests__/pages/broker-detail.test.tsx`) and possibly in any code that constructs a `BrokerConnection` literal. Note each error; they will be fixed in later tasks. Do **not** fix them in this task.

If the compiler reports errors **only** in test files and in the places listed in later tasks, proceed to commit. If it reports errors in places this plan doesn't yet touch, note them as an issue before committing.

- [ ] **Step 3.3: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/lib/api/types.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add label to BrokerConnection type

Follow-up tasks update the UI and tests to supply and display the field.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Frontend — Connect form with required label input

**Goal:** The Add Broker form requires a label, trims it, disables submit when invalid, and shows an inline error on 409.

**Files:**
- Modify: `frontend/app/(dashboard)/brokers/new/page.tsx`

### Steps

- [ ] **Step 4.1: Replace the connect form contents**

Overwrite `frontend/app/(dashboard)/brokers/new/page.tsx` with:

```tsx
"use client";
import {
  Box, Heading, Button, FormControl, FormLabel, Input, Select, VStack, useToast,
  FormErrorMessage,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";

const BROKER_FIELDS: Record<string, string[]> = {
  zerodha: ["api_key", "api_secret", "user_id"],
  exchange1: ["api_key", "private_key"],
  binance_testnet: ["api_key", "api_secret"],
};

const MAX_LABEL_LEN = 40;

export default function NewBrokerPage() {
  const router = useRouter();
  const toast = useToast();
  const [label, setLabel] = useState("");
  const [labelError, setLabelError] = useState<string | null>(null);
  const [brokerType, setBrokerType] = useState("");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fields = brokerType ? BROKER_FIELDS[brokerType] ?? [] : [];
  const trimmedLabel = label.trim();
  const labelValid = trimmedLabel.length > 0 && trimmedLabel.length <= MAX_LABEL_LEN;

  const handleFieldChange = (field: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brokerType || !labelValid) return;
    setSubmitting(true);
    setLabelError(null);
    try {
      await apiClient("/api/v1/brokers", {
        method: "POST",
        body: { broker_type: brokerType, label: trimmedLabel, credentials },
      });
      toast({ title: "Broker added", status: "success", duration: 3000 });
      router.push("/brokers");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setLabelError("A connection with this label already exists");
      } else {
        toast({ title: "Failed to add broker", status: "error", duration: 3000 });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box maxW="md">
      <Heading size="lg" mb={6}>Add Broker</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl isRequired isInvalid={labelError !== null}>
            <FormLabel>Label</FormLabel>
            <Input
              value={label}
              onChange={(e) => { setLabel(e.target.value); setLabelError(null); }}
              placeholder="e.g. Main Exchange1"
              maxLength={MAX_LABEL_LEN}
            />
            {labelError && <FormErrorMessage>{labelError}</FormErrorMessage>}
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Broker Type</FormLabel>
            <Select
              placeholder="Select broker"
              value={brokerType}
              onChange={(e) => {
                setBrokerType(e.target.value);
                setCredentials({});
              }}
            >
              <option value="zerodha">Zerodha</option>
              <option value="exchange1">Exchange1</option>
              <option value="binance_testnet">Binance Testnet</option>
            </Select>
          </FormControl>

          {fields.map((field) => (
            <FormControl key={field} isRequired>
              <FormLabel>{field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</FormLabel>
              <Input
                type="password"
                value={credentials[field] ?? ""}
                onChange={(e) => handleFieldChange(field, e.target.value)}
                placeholder={`Enter ${field}`}
              />
            </FormControl>
          ))}

          <Button
            type="submit"
            colorScheme="blue"
            isLoading={submitting}
            isDisabled={!brokerType || !labelValid || fields.some((f) => !credentials[f])}
          >
            Add Broker
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
```

- [ ] **Step 4.2: Typecheck**

(Note: `ApiError` is already exported from `lib/api/client.ts:29` as `export class ApiError extends Error` — no import fix needed.)

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no new errors introduced by this file. (Pre-existing test-file errors from Task 3 are still present; they'll be cleared in Task 5 and later.)

- [ ] **Step 4.3: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/app/\(dashboard\)/brokers/new/page.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): require a label when connecting a new broker

Adds a required, trimmed, 40-char Label input at the top of the connect
form with client-side validation and a 409 inline error.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Frontend — `RenameBrokerModal` + Brokers list page integration

**Goal:** The Brokers list card shows `label` as the title with `broker_type` as a small subtitle. A new pencil icon opens a reusable `RenameBrokerModal` that PATCHes the new label, triggers an SWR revalidation, and shows an inline 409 error inside the modal.

**Files:**
- Create: `frontend/components/brokers/RenameBrokerModal.tsx`
- Modify: `frontend/app/(dashboard)/brokers/page.tsx`
- Create: `frontend/__tests__/components/RenameBrokerModal.test.tsx`
- Modify: `frontend/__tests__/pages/brokers.test.tsx`

### Steps

- [ ] **Step 5.1: Write the failing `RenameBrokerModal` component tests**

Create `frontend/__tests__/components/RenameBrokerModal.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { RenameBrokerModal } from "@/components/brokers/RenameBrokerModal";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

function setup(overrides: Partial<React.ComponentProps<typeof RenameBrokerModal>> = {}) {
  const onClose = jest.fn();
  const onRenamed = jest.fn();
  render(
    <ChakraProvider>
      <RenameBrokerModal
        isOpen
        onClose={onClose}
        onRenamed={onRenamed}
        connectionId="conn-123"
        currentLabel="Old"
        {...overrides}
      />
    </ChakraProvider>,
  );
  return { onClose, onRenamed };
}

describe("RenameBrokerModal", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("prefills the current label", () => {
    setup();
    expect(screen.getByDisplayValue("Old")).toBeInTheDocument();
  });

  it("calls PATCH with the new trimmed label and invokes onRenamed", async () => {
    mockApiClient.mockResolvedValueOnce({});
    const { onRenamed } = setup();
    const input = screen.getByLabelText(/label/i);
    fireEvent.change(input, { target: { value: "  New Name  " } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1));
    expect(mockApiClient).toHaveBeenCalledWith(
      "/api/v1/brokers/conn-123",
      expect.objectContaining({ method: "PATCH", body: { label: "New Name" } }),
    );
    await waitFor(() => expect(onRenamed).toHaveBeenCalledTimes(1));
  });

  it("shows a 409 inline error without closing", async () => {
    const err = new clientModule.ApiError(409, {
      detail: "A broker connection with this label already exists",
    });
    mockApiClient.mockRejectedValueOnce(err);
    const { onClose, onRenamed } = setup();
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "Taken" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText(/already exists/i)).toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
    expect(onRenamed).not.toHaveBeenCalled();
  });

  it("disables save when label is blank", () => {
    setup({ currentLabel: "Old" });
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});
```

- [ ] **Step 5.2: Run the new tests and verify they fail**

Run:
```bash
cd frontend && npx jest __tests__/components/RenameBrokerModal.test.tsx
```
Expected: module-not-found error because `@/components/brokers/RenameBrokerModal` doesn't exist yet.

- [ ] **Step 5.3: Implement `RenameBrokerModal`**

Create `frontend/components/brokers/RenameBrokerModal.tsx`:

```tsx
"use client";
import {
  Button, FormControl, FormErrorMessage, FormLabel, Input,
  Modal, ModalBody, ModalCloseButton, ModalContent, ModalFooter, ModalHeader, ModalOverlay,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { ApiError, apiClient } from "@/lib/api/client";

const MAX_LABEL_LEN = 40;

export interface RenameBrokerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRenamed: () => void;
  connectionId: string;
  currentLabel: string;
}

export function RenameBrokerModal({
  isOpen,
  onClose,
  onRenamed,
  connectionId,
  currentLabel,
}: RenameBrokerModalProps) {
  const [label, setLabel] = useState(currentLabel);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setLabel(currentLabel);
      setError(null);
      setSaving(false);
    }
  }, [isOpen, currentLabel]);

  const trimmed = label.trim();
  const valid = trimmed.length > 0 && trimmed.length <= MAX_LABEL_LEN;

  const handleSave = async () => {
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/v1/brokers/${connectionId}`, {
        method: "PATCH",
        body: { label: trimmed },
      });
      onRenamed();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("A connection with this label already exists");
      } else {
        setError("Failed to rename broker");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Rename broker connection</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <FormControl isRequired isInvalid={error !== null}>
            <FormLabel>Label</FormLabel>
            <Input
              value={label}
              onChange={(e) => { setLabel(e.target.value); setError(null); }}
              maxLength={MAX_LABEL_LEN}
              placeholder="e.g. Main Exchange1"
            />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
        </ModalBody>
        <ModalFooter gap={2}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            colorScheme="blue"
            onClick={handleSave}
            isLoading={saving}
            isDisabled={!valid || trimmed === currentLabel}
          >
            Save
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

- [ ] **Step 5.4: Run the modal tests and verify they pass**

Run:
```bash
cd frontend && npx jest __tests__/components/RenameBrokerModal.test.tsx
```
Expected: the 4 modal tests pass.

Note: The "disables save when label is blank" test sets the label to whitespace. The `isDisabled` on the Save button also checks `trimmed === currentLabel` — an empty trim is not equal to "Old", so the disable is driven purely by `!valid` in that case. The assertion should hold.

- [ ] **Step 5.5: Update `brokers.test.tsx` — existing tests + new rename tests**

Replace the entire contents of `frontend/__tests__/pages/brokers.test.tsx` with:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokersPage from "@/app/(dashboard)/brokers/page";
import * as useApiModule from "@/lib/hooks/useApi";
import * as clientModule from "@/lib/api/client";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/lib/api/client", () => {
  const actual = jest.requireActual("@/lib/api/client");
  return { ...actual, apiClient: jest.fn() };
});

const mockApiClient = clientModule.apiClient as jest.Mock;

describe("BrokersPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("renders broker cards with label as title and broker_type as subtitle", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "1",
        broker_type: "zerodha",
        label: "Main Zerodha",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText("Main Zerodha")).toBeInTheDocument();
    expect(screen.getByText(/zerodha/i)).toBeInTheDocument(); // subtitle
    expect(screen.getByText("Add Broker")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [], isLoading: false, mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    expect(screen.getByText(/no broker/i)).toBeInTheDocument();
  });

  it("broker card links to detail page", () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-123",
        broker_type: "exchange1",
        label: "Ex1 Main",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    const link = screen.getByRole("link", { name: /Ex1 Main/i });
    expect(link).toHaveAttribute("href", "/brokers/broker-123");
  });

  it("edit button opens rename modal and saving calls PATCH + mutate", async () => {
    const mutate = jest.fn();
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-abc",
        broker_type: "exchange1",
        label: "Old Label",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate,
    });
    mockApiClient.mockResolvedValueOnce({});

    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    fireEvent.click(screen.getByLabelText(/rename/i));
    const input = screen.getByDisplayValue("Old Label");
    fireEvent.change(input, { target: { value: "New Label" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(mockApiClient).toHaveBeenCalledWith(
        "/api/v1/brokers/broker-abc",
        expect.objectContaining({ method: "PATCH", body: { label: "New Label" } }),
      ),
    );
    await waitFor(() => expect(mutate).toHaveBeenCalled());
  });

  it("keeps modal open with inline error on 409", async () => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-xyz",
        broker_type: "exchange1",
        label: "Old",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
      mutate: jest.fn(),
    });
    mockApiClient.mockRejectedValueOnce(
      new clientModule.ApiError(409, {
        detail: "A broker connection with this label already exists",
      }),
    );

    render(<ChakraProvider><BrokersPage /></ChakraProvider>);
    fireEvent.click(screen.getByLabelText(/rename/i));
    fireEvent.change(screen.getByDisplayValue("Old"), { target: { value: "Taken" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText(/already exists/i)).toBeInTheDocument(),
    );
    // Modal remains mounted — save button still visible
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 5.6: Run the page tests and verify they fail**

Run:
```bash
cd frontend && npx jest __tests__/pages/brokers.test.tsx
```
Expected: the "edit button" and "409" tests fail because the page doesn't yet render the rename button or modal.

- [ ] **Step 5.7: Update the Brokers list page**

Replace the entire contents of `frontend/app/(dashboard)/brokers/page.tsx` with:

```tsx
"use client";
import {
  Box, Heading, Flex, Button, IconButton, SimpleGrid, Card, CardHeader, CardBody, CardFooter,
  Text, useDisclosure, useToast,
} from "@chakra-ui/react";
import { MdEdit } from "react-icons/md";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EmptyState } from "@/components/shared/EmptyState";
import { RenameBrokerModal } from "@/components/brokers/RenameBrokerModal";
import { useBrokers } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils/formatters";

export default function BrokersPage() {
  const router = useRouter();
  const toast = useToast();
  const { data: brokers, isLoading, mutate } = useBrokers();
  const deleteDisclosure = useDisclosure();
  const renameDisclosure = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ id: string; label: string } | null>(null);
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
            <Card _hover={{ borderColor: "blue.400", cursor: "pointer" }} transition="border-color 0.15s">
              <CardHeader pb={2}>
                <Flex justify="space-between" align="start">
                  <Box>
                    <Text fontWeight="bold" fontSize="lg">{broker.label}</Text>
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
                <Button
                  size="xs"
                  colorScheme="red"
                  variant="ghost"
                  onClick={(e) => { e.preventDefault(); setDeleteTarget(broker.id); deleteDisclosure.onOpen(); }}
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
        onClose={() => { setDeleteTarget(null); deleteDisclosure.onClose(); }}
        onConfirm={handleDelete}
        title="Delete Broker"
        message="Are you sure you want to delete this broker connection? This action cannot be undone."
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
    </Box>
  );
}
```

- [ ] **Step 5.8: Run the page tests and verify they pass**

Run:
```bash
cd frontend && npx jest __tests__/pages/brokers.test.tsx
```
Expected: all 5 brokers page tests pass.

- [ ] **Step 5.9: Run the full frontend test suite to catch regressions**

Run:
```bash
cd frontend && npx jest
```
Expected: everything passes **except** `broker-detail.test.tsx`, which still has an outdated fixture (no `label`). That's fine — Task 6 fixes it.

If any test outside `broker-detail.test.tsx` fails, investigate before moving on.

- [ ] **Step 5.10: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/components/brokers/RenameBrokerModal.tsx \
        frontend/app/\(dashboard\)/brokers/page.tsx \
        frontend/__tests__/components/RenameBrokerModal.test.tsx \
        frontend/__tests__/pages/brokers.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): rename modal + show label as broker card title

Brokers list now renders the user-chosen label as the card title with
the broker_type as a small uppercase subtitle. A new pencil IconButton
opens a reusable RenameBrokerModal that PATCHes the new label, shows a
409 inline, and revalidates the list on success.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend — Broker detail page heading

**Goal:** Detail page heading renders `label`, with `broker_type` as a subtitle.

**Files:**
- Modify: `frontend/app/(dashboard)/brokers/[id]/page.tsx`
- Modify: `frontend/__tests__/pages/broker-detail.test.tsx`

### Steps

- [ ] **Step 6.1: Update `broker-detail.test.tsx` to expect the label as heading**

Edit `frontend/__tests__/pages/broker-detail.test.tsx`. Replace the `beforeEach` fixture and the heading test so that the mocked broker includes `label: "Main Ex1"` and the heading assertion expects `"Main Ex1"`:

```tsx
  beforeEach(() => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{
        id: "broker-abc",
        broker_type: "exchange1",
        label: "Main Ex1",
        is_active: true,
        connected_at: "2026-01-01",
      }],
      isLoading: false,
    });
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [], isLoading: false });
  });

  it("renders broker label in heading", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("heading", { name: "Main Ex1" })).toBeInTheDocument();
  });
```

(Leave the other three tests — stats bar, tab labels, back link — as-is.)

- [ ] **Step 6.2: Run the detail page test and verify it fails**

Run:
```bash
cd frontend && npx jest __tests__/pages/broker-detail.test.tsx -t "label in heading"
```
Expected: fails — heading currently renders `broker_type`, not `label`.

- [ ] **Step 6.3: Update the detail page to use label**

Edit `frontend/app/(dashboard)/brokers/[id]/page.tsx`. Change the header block (lines ~31-38) to:

```tsx
      <Flex align="center" gap={3} mb={6}>
        <Box>
          <Heading size="lg">{broker?.label ?? id}</Heading>
          {broker && (
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              {broker.broker_type}
            </Text>
          )}
        </Box>
        {broker && (
          <Badge colorScheme={broker.is_active ? "green" : "gray"}>
            {broker.is_active ? "Connected" : "Inactive"}
          </Badge>
        )}
      </Flex>
```

(Note: `Box` is already imported from `@chakra-ui/react` at the top of this file per `brokers/[id]/page.tsx:3` — no import change needed.)

- [ ] **Step 6.4: Run the detail page tests**

Run:
```bash
cd frontend && npx jest __tests__/pages/broker-detail.test.tsx
```
Expected: all four tests pass.

- [ ] **Step 6.5: Run the full frontend test suite**

Run:
```bash
cd frontend && npx jest
```
Expected: everything passes.

- [ ] **Step 6.6: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/app/\(dashboard\)/brokers/\[id\]/page.tsx \
        frontend/__tests__/pages/broker-detail.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): show label as broker detail page heading

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — Broker dropdowns (strategies + promote modal)

**Goal:** All three places that currently render a `BrokerConnection` in a `<Select>` dropdown show `{label} — {broker_type}` (plus `(Inactive)` where applicable).

**Files:**
- Modify: `frontend/app/(dashboard)/strategies/new/page.tsx:111-115`
- Modify: `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx:120-124`
- Modify: `frontend/components/deployments/PromoteModal.tsx:74-78`

### Steps

- [ ] **Step 7.1: Update `strategies/new/page.tsx` dropdown display**

Open `frontend/app/(dashboard)/strategies/new/page.tsx`. Find the existing map around line 111-115 that renders:

```tsx
              {(brokers ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.broker_type} ({b.is_active ? "Active" : "Inactive"})
                </option>
              ))}
```

Replace it with:

```tsx
              {(brokers ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.label} — {b.broker_type}{b.is_active ? "" : " (Inactive)"}
                </option>
              ))}
```

- [ ] **Step 7.2: Update `strategies/[id]/edit/page.tsx` dropdown display**

Open `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx`. Find the equivalent map around line 120-124 and apply the identical replacement:

```tsx
              {(brokers ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.label} — {b.broker_type}{b.is_active ? "" : " (Inactive)"}
                </option>
              ))}
```

- [ ] **Step 7.3: Update `components/deployments/PromoteModal.tsx` dropdown display**

Open `frontend/components/deployments/PromoteModal.tsx`. Find the existing map around line 74-78 that renders `{b.broker_type} ({b.id.slice(0, 8)}...)` and replace it with:

```tsx
                  {brokers?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label} — {b.broker_type}
                    </option>
                  ))}
```

(Keep any surrounding JSX — only the inner `<option>` content changes. If the existing structure differs slightly, preserve the outer wrapping and change only the `{b.broker_type} ({b.id.slice(0, 8)}...)` expression to `{b.label} — {b.broker_type}`.)

- [ ] **Step 7.4: Typecheck**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 7.5: Run the full frontend test suite**

Run:
```bash
cd frontend && npx jest
```
Expected: all tests pass. These three files have no dedicated tests, so this is just a regression check.

- [ ] **Step 7.6: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/app/\(dashboard\)/strategies/new/page.tsx \
        frontend/app/\(dashboard\)/strategies/\[id\]/edit/page.tsx \
        frontend/components/deployments/PromoteModal.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): show broker label in strategy + promote dropdowns

Replaces "{broker_type} (Active)" and "{broker_type} (<id prefix>…)"
with "{label} — {broker_type}" in the strategies/new, strategies/edit,
and PromoteModal broker dropdowns.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Deploy to production

**Goal:** The feature is live on `algomatter.in`. Existing rows show backfilled labels and can be renamed. New connections require a label.

**Files:** none (uses existing deploy skill).

### Steps

- [ ] **Step 8.1: Push the branch and open a PR (optional)**

If you're working on a feature branch, push it:
```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git push
```

If this plan is being executed directly on `main`, skip the push and proceed.

- [ ] **Step 8.2: Run the Alembic upgrade against the production database via the deploy flow**

Use the existing deploy skill: `/deploy`. The deploy skill is responsible for rsyncing the code, running `pip install --no-cache-dir .` inside the server's `.venv`, running `alembic upgrade head`, and restarting the systemd services.

Expected: the deploy output includes `Running upgrade b7d4e9f1a2c3 -> c8e1d2f3a4b5, broker_connection_label`.

- [ ] **Step 8.3: Verify the migration applied on prod**

Run (replacing DB credentials as needed from the Contabo compose file):
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 \
  'docker exec -it $(docker ps -qf name=postgres) psql -U algomatter -d algomatter -c "\d broker_connections"'
```
Expected: `label` column is present (`character varying(40)`, `not null`), and `ix_broker_connections_tenant_label` composite unique index is listed.

- [ ] **Step 8.4: Verify the two existing rows were backfilled correctly**

```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 \
  'docker exec -it $(docker ps -qf name=postgres) psql -U algomatter -d algomatter -c "SELECT id, broker_type, label FROM broker_connections;"'
```
Expected: both existing rows show labels like `exchange1 #f53cd578` and `exchange1 #b6a08109`.

- [ ] **Step 8.5: Smoke-test the UI**

Open https://algomatter.in, log in, and:
1. Go to **Brokers** — both cards should show the backfilled label as the title and `EXCHANGE1` as the subtitle.
2. Click the pencil icon on either card — a modal opens prefilled with the current label. Enter a new name, Save — card updates.
3. Try to rename the other card to the same new name — modal stays open with "already exists" error.
4. Click **Add Broker** — verify the Label field is required and the submit button is disabled until a valid label is entered.

- [ ] **Step 8.6: Check the `/api/v1/brokers` response directly**

```bash
# Assuming you have a JWT. Otherwise use the curl example from existing deploy skill docs.
curl -s -H "Authorization: Bearer $TOKEN" https://algomatter.in/api/v1/brokers | python3 -m json.tool
```
Expected: every object has a `label` field.

- [ ] **Step 8.7: Monitor the API logs for a minute**

```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 \
  'journalctl -u algomatter-api -f --no-pager -n 50'
```
Watch for any 5xx or Pydantic validation errors mentioning `label`. Ctrl-C to exit.

- [ ] **Step 8.8: Done — close the task list**

Mark Task 27 (the writing-plans handoff) complete and confirm with the user that the feature is live.
