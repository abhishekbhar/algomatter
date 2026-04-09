# Broker Connection Edit & Delete Design

**Date:** 2026-04-09

## Goal

Allow users to update broker credentials and reliably delete broker connections from the UI.

## Problem Statement

1. **Edit**: The UI only allows renaming the label (`RenameBrokerModal`). There is no way to update credentials (api_key, private_key, api_secret). Rotating keys requires deleting and re-creating the connection.
2. **Delete**: The delete button exists in the UI and the `DELETE /api/v1/brokers/{id}` endpoint exists, but the operation fails silently when the broker has linked records in `strategies`, `strategy_deployments`, or `manual_trades` — PostgreSQL rejects the delete due to missing `ondelete` clauses on all three foreign keys.

---

## Architecture

### Backend

#### 1. Database Migration

Add `ondelete` clauses to the three foreign keys that reference `broker_connections.id`:

| Table | Column | `ondelete` | Rationale |
|-------|--------|------------|-----------|
| `strategies` | `broker_connection_id` | `SET NULL` | Strategy record remains useful; FK is already nullable |
| `strategy_deployments` | `broker_connection_id` | `CASCADE` | Deployment is meaningless without its broker; FK is nullable |
| `manual_trades` | `broker_connection_id` | `CASCADE` | FK is non-nullable; trade record is tied to broker |

`DeploymentTrade` and `DeploymentState` already cascade off `StrategyDeployment` (`ondelete="CASCADE"`) so their records clean up automatically when deployments are removed.

Migration file: `algomatter/backend/app/db/migrations/versions/<rev>_broker_connection_ondelete.py`

Model updates in `algomatter/backend/app/db/models.py`:
```python
# strategies
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="SET NULL"), nullable=True
)

# strategy_deployments
broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="CASCADE"), nullable=True
)

# manual_trades
broker_connection_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("broker_connections.id", ondelete="CASCADE"), nullable=False
)
```

#### 2. Schema Update

File: `algomatter/backend/app/brokers/schemas.py`

`UpdateBrokerConnectionRequest` extended to accept optional `credentials`:

```python
class UpdateBrokerConnectionRequest(BaseModel):
    label: str | None = None
    credentials: dict | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateBrokerConnectionRequest":
        if self.label is None and self.credentials is None:
            raise ValueError("at least one of label or credentials must be provided")
        return self
```

`label` becomes optional (was required). Existing rename-only calls still work by omitting `credentials`.

#### 3. Endpoint Update

File: `algomatter/backend/app/brokers/router.py` — `PATCH /{connection_id}`

- If `body.label` is provided: update label (existing logic, including uniqueness check)
- If `body.credentials` is provided: re-encrypt with `encrypt_credentials(tenant_id, body.credentials)` and overwrite `conn.credentials`
- Both can be sent together or independently

---

### Frontend

#### 1. New Component: `UpdateCredentialsModal`

File: `algomatter/frontend/components/brokers/UpdateCredentialsModal.tsx`

Props:
```typescript
interface UpdateCredentialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
  connectionId: string;
  brokerType: string;
}
```

Behaviour:
- Renders credential fields from `BROKER_FIELDS[brokerType]` (same map as `new/page.tsx`):
  - `exchange1` → `api_key`, `private_key`
  - `binance_testnet` → `api_key`, `api_secret`
  - `zerodha` → `api_key`, `api_secret`, `user_id`
- All fields are `type="password"` inputs, all required
- User must re-enter all credentials (no partial update — avoids stale key mixing)
- On save: `PATCH /api/v1/brokers/{connectionId}` with `{ credentials: { ... } }`
- Error handling: generic toast on failure

#### 2. Broker List Page Updates

File: `algomatter/frontend/app/(dashboard)/brokers/page.tsx`

Changes:
- Import `UpdateCredentialsModal` and `MdKey` icon
- Add state: `credentialsTarget: { id: string; brokerType: string } | null`
- Add `credentialsDisclosure` via `useDisclosure()`
- Add a `MdKey` `IconButton` in each card's `CardFooter` (between rename and delete)
- Clicking the key icon sets `credentialsTarget` and opens `credentialsDisclosure`
- Update delete confirm modal message to:
  > "This will permanently delete the broker connection and all linked deployments and trade history. This action cannot be undone."
- Wire `UpdateCredentialsModal` with `credentialsTarget` state

---

## Data Flow

**Edit credentials:**
```
User clicks key icon → UpdateCredentialsModal opens →
User fills all credential fields → PATCH /api/v1/brokers/{id} { credentials: {...} } →
Backend re-encrypts and stores → 200 response → toast + onUpdated() → mutate()
```

**Delete:**
```
User clicks Delete → ConfirmModal (updated warning message) →
User confirms → DELETE /api/v1/brokers/{id} →
DB cascades: manual_trades deleted, strategy_deployments + their trades/state deleted,
strategies.broker_connection_id set to NULL →
204 response → toast + mutate()
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Credentials update fails | Toast: "Failed to update credentials" |
| Label already taken on rename | Existing 409 handling in `RenameBrokerModal` unchanged |
| Delete of non-existent broker | 404 → toast: "Failed to delete broker" |
| Unknown broker type in modal | `BROKER_FIELDS[brokerType] ?? []` → empty fields, save disabled |

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/db/migrations/versions/<rev>_broker_connection_ondelete.py` | New migration |
| `backend/app/db/models.py` | Add `ondelete` to 3 FK definitions |
| `backend/app/brokers/schemas.py` | `UpdateBrokerConnectionRequest` — both fields optional, validator requires at least one |
| `backend/app/brokers/router.py` | `PATCH` endpoint handles optional `credentials` |
| `frontend/lib/brokerFields.ts` | Extract `BROKER_FIELDS` map shared by new broker page and credentials modal |
| `frontend/components/brokers/UpdateCredentialsModal.tsx` | New component |
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Import `BROKER_FIELDS` from shared lib instead of inline |
| `frontend/app/(dashboard)/brokers/page.tsx` | Key icon button, credentials modal, updated delete message |

---

## Out of Scope

- Credential validation against the broker API on save (call-and-verify) — too complex for this iteration; user can test via the balance/quote endpoints
- Editing broker type — changing broker type would invalidate the credential schema; not supported
- Partial credential update (updating only one field) — requires all fields to avoid stale key mixing
