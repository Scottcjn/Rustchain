# Wallet transfer state guide

RustChain wallet APIs expose both **cryptographic verification** and **settlement state**. They are related, but they are not the same thing.

This guide explains the distinction using the public wallet endpoints documented in [`docs/API_REFERENCE.md`](API_REFERENCE.md).

## 1. A signed transfer can be valid and still be pending

`POST /wallet/transfer/signed` verifies an Ed25519-signed transfer request. A successful response can include:

```json
{
  "ok": true,
  "verified": true,
  "phase": "pending",
  "tx_hash": "abc123...",
  "amount_rtc": 1.5,
  "chain_id": "rustchain-mainnet-v2",
  "confirms_in_hours": 24
}
```

The important point is that `verified: true` means the signature and request were accepted by the transfer endpoint. It does **not** mean the transfer has completed settlement.

Treat `phase: "pending"` as a pending transfer until later state confirms otherwise.

## 2. Use wallet history to inspect lifecycle state

`GET /wallet/history` returns wallet-scoped transfer records. The API reference documents `status` values including:

- `pending`
- `confirmed`
- `failed`

A pending record can also expose `confirmed_at: null`, a future `confirms_at`, and `confirmations: 0`.

For tooling, dashboards, bounty payout checkers, and accounting code, the safest rule is:

> Do not equate a successful transfer submission with a confirmed transfer.

If your application needs to report settled activity, key that reporting to a confirmed state rather than the original submission response.

## 3. Suggested application state model

A small client can model the flow like this:

```text
signed request
    |
    v
verified + pending
    |
    +----> failed
    |
    v
confirmed
```

This prevents several common UI mistakes:

- showing a pending transfer as final,
- counting a pending payout as realised income,
- assuming `verified: true` means the recipient can already rely on settlement,
- hiding later failure state because the initial POST returned HTTP 200.

## 4. Example status check

```python
import requests

BASE_URL = "https://rustchain.org"
MINER_ID = "example-wallet"

history = requests.get(
    f"{BASE_URL}/wallet/history",
    params={"miner_id": MINER_ID, "limit": 20},
    timeout=15,
).json()

confirmed = [tx for tx in history if tx.get("status") == "confirmed"]
pending = [tx for tx in history if tx.get("status") == "pending"]
failed = [tx for tx in history if tx.get("status") == "failed"]

print("confirmed:", len(confirmed))
print("pending:", len(pending))
print("failed:", len(failed))
```

This example only reads the public wallet-history endpoint. It does not require an admin key or a private signing key.

## 5. Source of truth

For endpoint fields, authentication rules, response examples, and current error behaviour, use the canonical [RustChain API reference](API_REFERENCE.md), especially:

- `GET /wallet/history`
- `POST /wallet/transfer/signed`

If those endpoint contracts change, this guide should be updated to match them.
