# Exchange1 Futures Margin Modes

## Overview

Exchange1 Global supports two futures margin modes — **Cross** and **Isolated (Fix)** — but they behave very differently in practice and the account-level mode must be managed carefully.

---

## Margin Mode Behavior

### Cross Margin (`positionModel: "cross"`)

- Uses the shared futures wallet balance as margin
- **Works out of the box** — no special wallet setup required
- Default mode for all AlgoMatter order flows
- Required for the test account (Exchange1 demo/testnet account)

### Isolated Margin (`positionModel: "isolated"` → API: `"fix"`)

- Uses a per-symbol isolated wallet as margin
- Requires funds to be explicitly transferred to the isolated margin wallet on Exchange1
- **Will fail with `9008 Insufficient margin available`** if the isolated wallet is empty

---

## Critical: Account-Level Mode Lock

Exchange1 has an **account-level margin mode** that gets changed when you send an order with a different `positionModel`. This is a destructive side-effect:

| Scenario | What happens |
|----------|-------------|
| Send `positionModel: "fix"` order | Account switches to isolated mode, **even if the order is rejected** |
| Then send `positionModel: "cross"` order | Fails with `9050 Your current mode does not match, please switch and operate` |

Once the account is in isolated mode, **all cross orders are blocked** until the mode is manually switched back.

### Recovery

There is **no API endpoint** to switch margin modes programmatically (all `/set-margin-mode` paths return 404). Recovery must be done manually:

> **Exchange1 web interface → Futures → Margin Mode → Switch to Cross**

---

## Tested Error Codes

| Code | Message | Cause |
|------|---------|-------|
| `9008` | Insufficient margin available | Isolated wallet is empty; no funds allocated to isolated margin |
| `9050` | Your current mode does not match, please switch and operate | Account is in isolated mode but order sends `positionModel: "cross"` (or vice versa) |
| `9257` | null | Isolated margin wallet not initialized for the symbol |

---

## Test Results (2026-04-09)

All tests used BTCUSDT FUTURES, 1 contract (0.001 BTC), MARKET order type.

| # | position_model | position_side | Status | Error |
|---|---------------|---------------|--------|-------|
| T1 | isolated | long | rejected | `9008 Insufficient margin available` |
| T2 | isolated | (auto) | rejected | `9008 Insufficient margin available` |
| T3 | isolated | short | rejected | `9008 Insufficient margin available` |
| T4 | cross | long | rejected | `9050 mode mismatch` (account switched to isolated by T1) |
| T5 | cross | long | rejected | `9050 mode mismatch` (persists) |

**Conclusion:** The T1 isolated order changed the account mode to isolated even though the order itself was rejected (9008). All subsequent cross orders then failed.

---

## AlgoMatter Implementation Notes

### `_api_position_model()` in `exchange1.py`

```python
# "isolated" → "fix"   (Exchange1 term for isolated margin)
# "cross"    → "cross"
# None/other → "cross" (safe default)
```

The function defaults to `"cross"` for any unrecognized or missing `position_model`. This is intentional — isolated mode requires funded isolated wallets and can lock the account if misused.

### WebhookParameterBuilder Default

`position_model` defaults to `"cross"` in the webhook builder UI. **Do not change this to "isolated"** without first ensuring the isolated wallet is funded on Exchange1.

### When to Use Isolated Margin

Only use `position_model: "isolated"` when:
1. The isolated margin wallet for the target symbol has been funded on Exchange1
2. You have confirmed the account is already in isolated mode (to avoid the 9050 lock)

---

## Summary

For the current Exchange1 test account, **always use `position_model: "cross"`**. Isolated margin is an Exchange1-side configuration requirement and cannot be activated purely through AlgoMatter without first funding the isolated wallet on Exchange1's platform.
