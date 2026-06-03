# OTC Bridge — Settlement State Machine (async, crash-safe)

The OTC settlement flow is **asynchronous and atomicity-safe**: the on-chain RTC
payout is queued into the node's pending pool and confirms later, so the bridge
never reveals an HTLC preimage (or records a trade) until that payout is
**confirmed**. A background reconciler drives every in-flight order to a terminal
state, recovering from a crash at any point.

## States

| status | meaning | terminal? |
|--------|---------|-----------|
| `open` | resting order on the book | no |
| `matched` | taker matched; awaiting the seller's HTLC-secret confirm | no |
| `settling` | confirm claimed the order; escrow release + payout in progress | transient |
| `payout_pending` | escrow released, RTC payout **queued but not yet confirmed** — secret **withheld** | transient |
| `settlement_recovery` | escrow released but settlement couldn't finalize cleanly — operator/reconciler will re-drive (payout is idempotent) | recovery |
| `refund_pending` | order ended (cancel/expiry); escrow refund queued but not yet confirmed | transient |
| `completed` | payout **confirmed**; trade recorded; HTLC secret released | yes |
| `cancelled` / `expired` | order ended; escrow refunded | yes |

`settling`, `payout_pending`, `refund_pending`, and `settlement_recovery` are all
driven to terminal by **`reconcile_settlements()`** (startup pass + timer +
`POST /admin/reconcile`). Reconciliation is **leader-locked** (one worker at a
time) and **idempotent** — the worker payout is keyed `otc_payout:<order_id>`, so
re-driving never double-pays, and refunds are no-ops on an already-refunded job.

## `POST /api/orders/<id>/confirm` — response contract (CHANGED in v3)

`ok` now means **the swap is fully, atomically complete** — payout confirmed,
trade recorded, secret released. It is **no longer** "the confirm was accepted".

| outcome | HTTP | `ok` | `status` | `htlc_secret` |
|---------|------|------|----------|----------------|
| payout **confirmed** | 200 | `true` | `completed` | **present** |
| payout **queued** (normal) | 200 | `false` | `payout_pending` | withheld |
| escrow untouched (retryable) | 200 | `false` | `matched` | — |
| escrow released, payout failed | 200 | `false` | `settlement_recovery` | — |
| claim lost after confirmed payout | 409 | `false` | `settlement_recovery` | — |

**Client integration:** on `status == "payout_pending"`, do **not** treat the swap
as done. Poll **`GET /api/orders/<id>`** until `status == "completed"`, then read
`htlc_secret` from that response (it is exposed only for `confirmed`/`completed`
orders). A queued payout typically confirms within the node's pending window.

## `POST /api/orders/<id>/cancel` — response contract (CHANGED in v3)

For **escrow-bearing** orders, cancel first commits `refund_pending`, then refunds:

| outcome | `status` | `escrow_refunded` |
|---------|----------|-------------------|
| refund landed | `cancelled` | `true` |
| refund queued/failed | `refund_pending` | `false` (reconciler retries) |

Non-escrow cancels are terminal `cancelled` immediately.

## Configuration

| env | default | purpose |
|-----|---------|---------|
| `OTC_RECONCILE_INTERVAL_SECONDS` | `60` | reconciler timer; `0` disables the timer (startup pass still runs; drive via `POST /admin/reconcile`) |
| `OTC_SETTLEMENT_STUCK_SECONDS` | `120` | how long a `settling` row must be idle before reconciliation acts on it |

Invalid values fall back to the default (never crash the worker). The reconciler
starts **lazily on the first HTTP request** (never at import), so importing the
module for tests/CLI has no side effects.

## Why this shape

A pre-v3 confirm revealed the preimage on a payout that was only **queued**. A
queued payout can still be voided, so the counterparty could claim the quote side
off the revealed secret while the RTC payout never landed — a one-sided loss.
Gating the secret on a **confirmed** payout, plus durable transient states a
reconciler can always resume, makes the swap atomic across a crash at any step.
