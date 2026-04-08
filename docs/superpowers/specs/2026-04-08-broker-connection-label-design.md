# Broker Connection Label — Design

**Date:** 2026-04-08
**Status:** Draft — pending user review

## Problem

The `broker_connections` table exposes only `id`, `broker_type`, `is_active`, and `connected_at` via its API response. Users who connect two accounts to the same broker (e.g. two `exchange1` keys for separate trading wallets) cannot distinguish them in any of the places the UI renders a connection: the Brokers list, the broker detail page, the strategy-new dropdown, or the deployment promote modal. The only differentiator today is a truncated UUID, which is unreadable. This blocks multi-account workflows and risks users sending an order to the wrong account.

## Goals

- A user-chosen, human-readable label is stored per broker connection.
- The label is shown everywhere a broker connection is currently rendered.
- Labels are unique within a tenant so they always identify exactly one connection.
- Users can rename a connection without deleting and re-creating it (which would require re-entering API keys).
- Existing connections are backfilled automatically with a unique, non-empty label so the new `NOT NULL` column is safe.

## Non-goals

- Free-form description / notes field.
- Color / icon / avatar customization.
- Labeling other entities (strategies, deployments).
- Soft-delete semantics.
- Full audit log of label changes.

## Data model

New column on the existing `broker_connections` table:

```
label  VARCHAR(40)  NOT NULL
```

**Alembic migration** (new revision, parent = current head):

1. `op.add_column("broker_connections", sa.Column("label", sa.String(40), nullable=True))`
2. Backfill every existing row with `f"{broker_type} #{id[:8]}"`
   (e.g. `exchange1 #f53cd578`). Because `id` is a UUID, the 8-char prefix is
   unique within a tenant with overwhelming probability, and in practice unique
   across the entire table for the current deployment.
3. `op.alter_column("broker_connections", "label", nullable=False)`
4. `op.create_index("ix_broker_connections_tenant_label", "broker_connections",
   ["tenant_id", "label"], unique=True)`

Downgrade drops the index and the column.

**Model change** in `app/db/models.py`:

```python
label: Mapped[str] = mapped_column(String(40), nullable=False)
```

## API

### Schemas (`app/brokers/schemas.py`)

```python
def validate_label(v: str) -> str:
    stripped = v.strip()
    if not stripped:
        raise ValueError("label cannot be blank")
    if len(stripped) > 40:
        raise ValueError("label cannot exceed 40 characters")
    return stripped

class CreateBrokerConnectionRequest(BaseModel):
    broker_type: str
    label: str            # NEW — required
    credentials: dict
    _validate_label = field_validator("label")(validate_label)

class UpdateBrokerConnectionRequest(BaseModel):   # NEW
    label: str
    _validate_label = field_validator("label")(validate_label)

class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    label: str            # NEW
    is_active: bool
    connected_at: datetime
```

### Endpoints (`app/brokers/router.py`)

| Method | Path | Change |
|---|---|---|
| `POST` | `/api/v1/brokers` | Accept & persist `label`. On `IntegrityError` from the unique index → HTTP 409 with detail `"A broker connection with this label already exists"`. |
| `GET` | `/api/v1/brokers` | Include `label` in every response (covered by schema change). |
| `PATCH` | `/api/v1/brokers/{connection_id}` | **NEW** — body: `UpdateBrokerConnectionRequest`. Tenant-scoped load (404 if missing), assigns `label`, commits. On `IntegrityError` → HTTP 409 (same message as create). On success → HTTP 200 with updated `BrokerConnectionResponse`. |
| `DELETE` | `/api/v1/brokers/{connection_id}` | No change. |

All five existing `GET /{connection_id}/…` detail endpoints (balance, quote, stats, positions, orders, trades) return their own response shapes and need no changes.

Renaming a row to its *own* current label is a no-op and must return 200 (not 409). PostgreSQL's unique constraint permits updating a row to the same value it already holds, so no special handling is needed.

## Frontend

### TypeScript type (`lib/api/types.ts`)

```ts
export interface BrokerConnection {
  id: string;
  broker_type: string;
  label: string;        // NEW
  is_active: boolean;
  connected_at: string;
}
```

### Connect form — `app/(dashboard)/brokers/new/page.tsx`

Add a required "Label" text field at the top (above Broker Type). Client-side
validation mirrors the backend: trim, 1–40 chars, reject whitespace-only.
Submit button disabled if invalid. On 409 from the server, show inline error
"A connection with this label already exists".

### List page — `app/(dashboard)/brokers/page.tsx`

- Card title becomes `broker.label` (bold, `fontSize="lg"`).
- `broker_type` becomes a small secondary label underneath:
  `<Text fontSize="xs" color="gray.500" textTransform="uppercase">{broker.broker_type}</Text>`.
- Add an edit (pencil) icon button in the card footer next to Delete. Clicking
  opens a small modal with a single text input prefilled with the current
  label; Save calls `PATCH /api/v1/brokers/{id}` and `mutate()`s the list.
  Duplicate → inline error inside the modal.

### Detail page — `app/(dashboard)/brokers/[id]/page.tsx`

- Heading becomes `broker?.label ?? id`.
- `broker_type` shown as a small subtitle beneath the heading.

### Dropdowns

- `strategies/new/page.tsx:113` → `{b.label} — {b.broker_type}{b.is_active ? "" : " (Inactive)"}`
- `components/deployments/PromoteModal.tsx:76` → `{b.label} — {b.broker_type}` (replaces the `id.slice(0,8)` hack)
- `strategies/[id]/edit/page.tsx:122` → same treatment (already renders `{b.broker_type} (Active/Inactive)`)

## Validation & error handling

Three layers, in order:

1. **Frontend (UX)** — create form and rename modal: trim, require non-empty
   after trim, cap at 40 chars, disable submit when invalid, inline error on
   invalid submission.
2. **Pydantic schemas (API boundary)** — shared `validate_label` helper applied
   to both `CreateBrokerConnectionRequest` and `UpdateBrokerConnectionRequest`
   via `@field_validator`. Strips, requires non-empty, caps at 40. Violation →
   HTTP 422 (FastAPI default).
3. **Database (hard guarantee)** — unique composite index on
   `(tenant_id, label)`. Concurrent writes: one wins, the other raises
   `IntegrityError`. Router catches `IntegrityError` specifically and
   re-raises as HTTP 409 with detail
   `"A broker connection with this label already exists"`.

**Backfill safety:** the migration runs the `UPDATE ... SET label = ...`
statement before the `NOT NULL` alter and unique index creation. Because `id`
is a UUID and unique, backfilled labels are guaranteed unique within any
tenant, so the subsequent index creation will not fail on existing data.

## Testing

### Backend — `algomatter/backend/tests/test_brokers.py` (extend / create)

1. `test_create_broker_connection_requires_label` — POST without `label` → 422.
2. `test_create_broker_connection_rejects_blank_label` — POST with `label="   "` → 422.
3. `test_create_broker_connection_rejects_too_long_label` — POST with `label="x"*41` → 422.
4. `test_create_broker_connection_trims_whitespace` — POST with `label="  Main  "` → 201, persisted value `"Main"`.
5. `test_create_broker_connection_duplicate_label_returns_409` — same label twice in one tenant → second → 409.
6. `test_create_broker_connection_same_label_different_tenants_ok` — two tenants both use `"Main"` → both 201.
7. `test_patch_broker_connection_renames_label` — happy path, returns updated body.
8. `test_patch_broker_connection_rename_to_existing_returns_409` — A and B in same tenant; PATCH B.label = A.label → 409.
9. `test_patch_broker_connection_rename_to_own_current_label_is_ok` — PATCH A.label = A.label → 200.
10. `test_patch_broker_connection_not_found_returns_404` — unknown id → 404.
11. `test_patch_broker_connection_other_tenant_returns_404` — other tenant's connection → 404 (tenant isolation).
12. `test_list_broker_connections_includes_label` — GET returns `label` on every row.

### Migration verification

Manual check after running the upgrade in a dev DB: existing rows have
non-empty, unique labels; unique index exists; downgrade removes both cleanly.

### Frontend — `algomatter/frontend/__tests__/`

1. `pages/brokers.test.tsx` — card title renders `broker.label`, `broker_type` appears as subtitle.
2. `pages/brokers.test.tsx` — edit icon opens modal; save calls `PATCH` and triggers `mutate()`.
3. `pages/brokers.test.tsx` — 409 response keeps modal open with inline error.
4. Connect form test — submitting without a label is blocked; leading/trailing spaces are trimmed on submit.
5. `pages/broker-detail.test.tsx` — heading renders `broker.label`.
6. Dropdown tests (`strategies/new`, `PromoteModal`) — update fixtures to include `label`; assert the new format `"{label} — {broker_type}"` renders.

### TDD order

For each unit of work, write the failing test first, verify it fails, implement,
verify it passes. Start with the `validate_label` helper (zero dependencies),
then the migration, then the endpoints, then the frontend.

## Affected files (exhaustive list)

**Backend**
- `algomatter/backend/app/db/migrations/versions/<new>_broker_connection_label.py` (new)
- `algomatter/backend/app/db/models.py`
- `algomatter/backend/app/brokers/schemas.py`
- `algomatter/backend/app/brokers/router.py`
- `algomatter/backend/tests/test_brokers.py` (new or extended)

**Frontend**
- `algomatter/frontend/lib/api/types.ts`
- `algomatter/frontend/app/(dashboard)/brokers/new/page.tsx`
- `algomatter/frontend/app/(dashboard)/brokers/page.tsx`
- `algomatter/frontend/app/(dashboard)/brokers/[id]/page.tsx`
- `algomatter/frontend/app/(dashboard)/strategies/new/page.tsx`
- `algomatter/frontend/app/(dashboard)/strategies/[id]/edit/page.tsx`
- `algomatter/frontend/components/deployments/PromoteModal.tsx`
- `algomatter/frontend/__tests__/pages/brokers.test.tsx`
- `algomatter/frontend/__tests__/pages/broker-detail.test.tsx`
- New tests as described above

## Deployment

Standard deploy flow:
1. Run Alembic upgrade against the prod DB (adds column, backfills, sets `NOT NULL`, creates unique index).
2. Deploy backend (`algomatter-api`, `algomatter-worker`, `algomatter-strategy-runner`) via the existing deploy skill.
3. Deploy frontend (`algomatter-frontend`).

No downtime is required because the migration is additive and the API change is backwards-compatible at the column level (old clients that don't send `label` get a 422 — which is acceptable because only the AlgoMatter frontend talks to this endpoint and it will be updated in the same deploy).
