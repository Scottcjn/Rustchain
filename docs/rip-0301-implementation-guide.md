# RIP-0301 Implementation Guide

| Field | Value |
|-------|-------|
| **RIP** | 0301 |
| **Document** | Phase-2 Implementation Guide |
| **Covers** | §8 Open Questions (1–5) |
| **Status** | **DRAFT — Implementation RFC** |
| **Created** | 2026-07-03 |
| **Reference impl** | `rips/reference/rip0301_atlas_deed_atomicity.py` |

---

## 1. Tip Maturation: Chain Event vs. Off-Chain Ledger Anchored On-Chain

### Context

Phase-1 uses a single-authority ledger for tip maturation. Phase-2 must make
maturation safe across RustChain's multi-node deployment. Two models exist:

| Model | Description | Tradeoffs |
|-------|-------------|-----------|
| **Pure chain event** | Every tip, allowance, and maturation is a transaction applied deterministically by all nodes. | Full determinism; high gas cost; block bloat from high-volume tip traffic. |
| **Off-chain ledger anchored on-chain** | An off-chain service (or per-node store) tracks tip state; periodic checkpoints are committed on-chain for settlement. | Gas-efficient; faster tip throughput; relies on anchor integrity; requires dispute window. |

### Recommendation: Hybrid — Chain-Anchored State Commitments

A hybrid model captures determinism where it matters (settlement) while keeping
high-frequency tip operations cheap:

```
  Tip (off-chain)  ──►  Maturation window  ──►  Anti-abuse pass  ──►  Checkpoint tx (on-chain)
       │                        │                       │                       │
  recorded locally         tracked locally         runs locally          commit settles
  per Beacon identity     per Beacon identity     per Beacon identity   RTC debits on-chain
```

#### Data Structures

```python
@dataclass
class TipRecord:
    tip_id: str
    sender_beacon: str       # Beacon identity of sender
    recipient_beacon: str    # Beacon identity of recipient
    artifact_id: str         # What was tipped (agent, parcel, content)
    amount_credits: int      # Tip Credit amount (non-transferable)
    created_at: int          # Unix timestamp
    matured_at: int | None   # None until settlement
    settled: bool            # True after checkpoint tx confirms

@dataclass
class MaturationCheckpoint:
    checkpoint_id: str
    epoch_height: int        # Block height at checkpoint
    settled_tips: list[TipRecord]
    rtc_debited: int         # Total micro-RTC debited from founder_community
    pool_balance_after: int  # Pool balance post-debit
    merkle_root: str         # Root of settled tips for verification
    signature: str           # Authority signature (initially single-authority; later multi-sig)
```

#### Settlement Flow

1. **Off-chain accumulation (0–48h):** Tips are recorded locally per node.
   Nodes validate tip rules (no self-tip, attested sender) before recording.
2. **Maturation window:** Configurable (default 48h). During this window the
   anti-abuse pass (§6) evaluates each tip.
3. **Checkpoint transaction:** At each epoch boundary (or configurable interval),
   a `MaturationCheckpoint` transaction is submitted. It includes:
   - The merkle root of all settled tips in this epoch.
   - The total `rtc_debited` from `founder_community`.
   - The post-settlement pool balance for verification.
4. **On-chain settlement:** The node applies the checkpoint atomically — debiting
   `founder_community` and crediting recipients. All nodes verify the merkle root
   against their local tip records before applying.

#### Why Hybrid

- **Determinism at settlement:** The checkpoint transaction is a single atomic
  operation that all nodes apply identically.
- **Gas efficiency:** Individual tips are not on-chain; only the epoch summary
  is committed.
- **Auditability:** The merkle root allows any node or observer to verify which
  tips were included without replaying every tip.
- **Graceful degradation:** If the pool is exhausted during a checkpoint, the
  remaining tips fall back to reputation-only (never mint, never overdraw).

#### Migration from Phase-1

The Phase-1 single-authority ledger's `TipCredit` model maps directly to
`TipRecord`. The `tip_maturation_window` config parameter carries over. The
authority interface (`IdentityOracle`, `FundingPool`) is already injected, so
Phase-2 replaces the oracle with the on-chain Beacon registry and the pool with
the `founder_community` debit guard without touching core logic.

---

## 2. Hardware Attestation Binding to Beacon Identity (Replay Prevention)

### Context

RIP-PoA ties mining rewards to hardware attestation. For tip credits, we must
ensure one physical device maps to exactly one Beacon identity, preventing
sybil attacks where one device creates multiple Beacon identities to drain
the tip pool.

### Recommendation: Nonce-Based One-to-One Binding

#### Binding Protocol

```
  Registration Phase:
  ─────────────────
  1. Device generates TPM-derived keypair (or equivalent hardware root of trust)
  2. Device sends attestation certificate + public key to Beacon registry
  3. Beacon registry verifies attestation (matches known hardware fingerprint)
  4. Registry generates a BINDING_NONCE (random 32-byte value, stored on-chain)
  5. Device signs the BINDING_NONCE with its TPM keypair
  6. Registry stores { beacon_id, public_key, binding_nonce, signature, epoch }
  7. Binding is IMMUTABLE after confirmation (no re-binding without burn+re-register)

  Attestation Verification (per-tip or per-epoch):
  ────────────────────────────────────────────────
  1. Device presents current attestation + epoch number
  2. Registry verifies: (a) public key matches stored key for beacon_id
  3. Registry verifies: (b) attestation epoch is within current epoch window
  4. Registry verifies: (c) no duplicate public_key exists for any other beacon_id
  5. If any check fails → attestation rejected, tips from this identity cannot mature
```

#### Data Structures

```python
@dataclass
class BeaconAttestation:
    beacon_id: str
    public_key: bytes           # TPM-derived public key
    binding_nonce: bytes        # 32-byte random, stored on-chain
    signature: bytes            # sign(binding_nonce, tpm_key)
    registered_epoch: int       # Epoch at registration
    attestation_epoch: int      # Latest verified epoch
    status: str                 # "active" | "revoked" | "burned"

@dataclass
class EpochAttestationWindow:
    epoch_number: int
    start_slot: int
    end_slot: int
    attested_beacons: list[str]  # Beacons with valid attestation this epoch
```

#### Replay Prevention

1. **Nonce-based binding:** Each registration uses a unique `binding_nonce`.
   Even if an attacker captures the registration signature, they cannot reuse it
   for a second identity because the nonce is already bound.

2. **Epoch-bound attestation windows:** Attestations are valid for one epoch
   (configurable, default 144 slots = ~24h). At each epoch boundary, devices
   must re-attest. This limits the window for replay attacks.

3. **One-to-one enforcement:** The registry maintains a `public_key → beacon_id`
   mapping. Any attempt to register a second beacon_id with the same public key
   is rejected. Any attempt to register a beacon_id with a public key already
   bound to another beacon_id is rejected.

4. **Burn-to-rebind:** If a device needs to re-register (e.g., hardware
   replacement), the old binding must be explicitly "burned" (revoked on-chain),
   and a new registration with a new TPM keypair is required. The old beacon_id
   retains its reputation but loses attestation status.

#### Anti-Sybil Properties

- One TPM = one beacon_id at any time (enforced at registration).
- Re-registration requires burn + new TPM keypair (costly to fake).
- Software-only agents can still tip and receive reputation, but their received
  tips never mature (no pool-draining vector from non-attested identities).

---

## 3. Pool Draining Detection Without Punishing Legitimate Patronage

### Context

The `founder_community` pool is finite (125,829 RTC). Many-to-one patterns
(sybil tipping) could drain it, but legitimate patronage (a popular creator
receiving tips from many fans) must not be penalized.

### Recommendation: Sliding Window Entropy-Based Scoring

Instead of hard caps (which create arbitrary cliffs), use a composite score
that considers sender diversity, temporal distribution, and volume patterns.

#### Composite Score Components

```python
@dataclass
class DrainScore:
    beacon_id: str
    window_start: int           # Unix timestamp
    window_end: int             # Unix timestamp
    sender_diversity: float     # 0.0–1.0 (unique senders / expected senders)
    temporal_entropy: float     # 0.0–1.0 (entropy of tip timestamps)
    volume_concentration: float # 0.0–1.0 (inverse of Gini coefficient)
    composite_score: float      # Weighted average
    classification: str         # "normal" | "suspicious" | "blocked"
```

#### Scoring Algorithm

```python
WINDOW_SIZE = 86400 * 7  # 7-day sliding window
DIVERSITY_WEIGHT = 0.4
TEMPORAL_WEIGHT = 0.3
VOLUME_WEIGHT = 0.3
SUSPICIOUS_THRESHOLD = 0.7   # Composite above this → suspicious
BLOCKED_THRESHOLD = 0.9      # Composite above this → blocked (tips become reputation-only)

def compute_drain_score(
    tips: list[TipRecord],
    recipient: str,
    window_end: int,
) -> DrainScore:
    window_start = window_end - WINDOW_SIZE
    window_tips = [t for t in tips if t.recipient_beacon == recipient
                   and window_start <= t.created_at <= window_end]

    if not window_tips:
        return DrainScore(recipient, window_start, window_end, 0, 0, 0, 0, "normal")

    # 1. Sender diversity
    unique_senders = len(set(t.sender_beacon for t in window_tips))
    expected = max(1, len(window_tips) ** 0.5)  # Heuristic: sqrt(N) expected
    diversity = min(1.0, unique_senders / expected)

    # 2. Temporal entropy (tips spread across time → higher entropy)
    timestamps = [t.created_at for t in window_tips]
    entropy = _shannon_entropy(timestamps, bucket_size=3600)  # 1-hour buckets

    # 3. Volume concentration (Gini coefficient)
    amounts = [t.amount_credits for t in window_tips]
    gini = _gini_coefficient(amounts)
    concentration = 1.0 - gini  # Invert: high Gini = high concentration = bad

    composite = (
        DIVERSITY_WEIGHT * diversity
        + TEMPORAL_WEIGHT * entropy
        + VOLUME_WEIGHT * concentration
    )

    if composite >= BLOCKED_THRESHOLD:
        classification = "blocked"
    elif composite >= SUSPICIOUS_THRESHOLD:
        classification = "suspicious"
    else:
        classification = "normal"

    return DrainScore(
        recipient, window_start, window_end,
        diversity, entropy, concentration,
        composite, classification,
    )
```

#### Why This Works

- **Legitimate patronage** (fans tipping a creator): High sender diversity,
  natural temporal spread, moderate volume concentration → low composite score.
- **Sybil draining** (fake accounts tipping one account): Low diversity (few
  real actors behind fake accounts), bursty timing, high volume concentration
  → high composite score.
- **No hard caps:** The continuous score avoids arbitrary thresholds that
  create attack vectors at the boundary.
- **Sliding window:** Prevents gaming by timing tips across epoch boundaries.

#### Integration with Maturation

During the anti-abuse pass (§5 step 4), each recipient's `DrainScore` is
computed. Tips classified as "blocked" are voided (become reputation-only).
Tips classified as "suspicious" are de-weighted (50% maturation value).
Tips classified as "normal" mature fully.

---

## 4. `founder_community` Debit Guard Integration

### Context

`founder_community` holds 125,829 RTC (1.5% of total supply). RIP-0004
establishes a 1-year unlock delay for premine wallets. Tip maturation debits
from this pool must respect the existing unlock guard to prevent early-release
bypass.

### Recommendation: Sub-Category Unlock Schedule

The existing lock ledger (`node/lock_ledger.py`) supports typed locks with
`unlock_at` timestamps. We extend this with a new `LockType` for tip maturation
debits, ensuring they are subject to the same 1-year constraint while maintaining
separate accounting.

#### Extended Lock Types

```python
class LockType(Enum):
    BRIDGE_DEPOSIT = "bridge_deposit"
    BRIDGE_WITHDRAW = "bridge_withdraw"
    EPOCH_SETTLEMENT = "epoch_settlement"
    ADMIN_HOLD = "admin_hold"
    TIP_MATURATION = "tip_maturation"         # NEW: RIP-0301
    FOUNDER_COMMUNITY_VEST = "founder_community_vest"  # NEW: 1-year guard
```

#### Debit Guard Flow

```
  Maturation Checkpoint
       │
       ▼
  ┌─────────────────────────────────────────┐
  │ 1. Query founder_community balance     │
  │ 2. Check TIP_MATURATION locks:         │
  │    - Sum of pending (locked) debits     │
  │    - Sum of settled (unlocked) debits   │
  │ 3. Available = balance - pending_locks  │
  │ 4. If rtc_debited > available:          │
  │    - Partially settle (reduce credits)  │
  │    - Remainder → reputation-only        │
  │ 5. Create TIP_MATURATION lock for:     │
  │    - Amount = rtc_debited               │
  │    - unlock_at = now + 1_YEAR_SECONDS   │
  │ 6. Debit founder_community balance      │
  └─────────────────────────────────────────┘
```

#### Data Structures

```python
# New entry in the existing lock_ledger schema
@dataclass
class TipMaturationLock:
    id: int
    checkpoint_id: str        # Links to MaturationCheckpoint
    amount_i64: int           # Micro-RTC debited
    locked_at: int            # Unix timestamp
    unlock_at: int            # locked_at + 365 days
    status: str               # "locked" | "released" | "forfeited"

# Constants
ONE_YEAR_SECONDS = 365 * 24 * 3600
FOUNDER_COMMUNITY_WALLET = "founder_community"
```

#### Integration Points

1. **Lock creation (at checkpoint settlement):**
   ```python
   def settle_checkpoint(conn, checkpoint: MaturationCheckpoint):
       available = _balance_i64_for_wallet(conn, FOUNDER_COMMUNITY_WALLET)
       pending_locks = _sum_pending_locks(conn, LockType.TIP_MATURATION)
       free_balance = available - pending_locks

       if checkpoint.rtc_debited > free_balance:
           # Partial settlement — reduce rtc_debited to free_balance
           checkpoint.rtc_debited = free_balance
           # Remaining tips become reputation-only

       _debit_wallet_atomic(conn, FOUNDER_COMMUNITY_WALLET, checkpoint.rtc_debited, ...)
       create_lock(
           conn,
           miner_id=FOUNDER_COMMUNITY_WALLET,
           amount_i64=checkpoint.rtc_debited,
           lock_type=LockType.TIP_MATURATION,
           unlock_at=int(time.time()) + ONE_YEAR_SECONDS,
       )
   ```

2. **Guard enforcement:**
   The existing `release_lock()` function in `lock_ledger.py` already checks
   `unlock_at` before allowing release (line 262: `if now < unlock_at and
   released_by != "admin"`). No changes needed — the guard is inherited.

3. **Pool exhaustion:**
   If `founder_community` balance approaches zero, the system gracefully
   degrades: tips remain valid as pure reputation, and the checkpoint
   settles zero RTC. The pool never overdraws because the debit guard
   checks available balance before every settlement.

#### Why Reuse the Existing Guard

- The 1-year unlock delay is already enforced on-chain for premine wallets.
- The `lock_ledger.py` module provides `create_lock()`, `release_lock()`,
  `get_pending_unlocks()`, and `forfeit_lock()` — all the primitives needed.
- No new consensus rules are required; the existing guard is compositional.

---

## 5. Atlas Deed Atomicity — Multi-Surface Commit Protocol

### Context

Atlas deed transfers must be atomic across the node, BoTTube, and Sophiacord
surfaces. The reference implementation (`rips/reference/rip0301_atlas_deed_atomicity.py`)
models this as a deterministic event builder that requires settled RTC receipts
from all three surfaces before any owner map change. This guide specifies the
full commit protocol.

### Recommendation: Three-Phase Commit (Prepare → Commit → Verify)

#### Protocol Overview

```
  Buyer initiates transfer
       │
       ▼
  ┌──────────────────┐
  │ Phase 1: PREPARE │  Each surface observes the RTC settlement and
  │                  │  creates a SurfaceReceipt (parcel_id, seller,
  │                  │  buyer, settlement_tx_id, settled=True)
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Phase 2: COMMIT  │  Coordinator collects all 3 receipts.
  │                  │  If all agree → build AtlasDeedTransfer event.
  │                  │  If any disagree → abort, seller retains ownership.
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Phase 3: VERIFY  │  Each surface applies the event to its owner map.
  │                  │  If any surface fails → rollback all surfaces.
  └──────────────────┘
```

#### Surface Receipt Generation

Each surface independently observes the RTC settlement transaction and
generates a receipt:

```python
# Node surface (authoritative — reads from chain)
def node_receipt(parcel_id, seller, buyer, settlement_tx_id) -> SurfaceReceipt:
    # Verify settlement_tx_id exists on-chain
    # Verify amounts match expected price
    return SurfaceReceipt(
        surface="node",
        parcel_id=parcel_id,
        seller=seller,
        buyer=buyer,
        settlement_asset="RTC",
        settlement_tx_id=settlement_tx_id,
        settled=True,
    )

# BoTTube surface (content ownership)
def bottube_receipt(parcel_id, seller, buyer, settlement_tx_id) -> SurfaceReceipt:
    # Verify the content ownership record matches
    return SurfaceReceipt(
        surface="bottube",
        parcel_id=parcel_id,
        seller=seller,
        buyer=buyer,
        settlement_asset="RTC",
        settlement_tx_id=settlement_tx_id,
        settled=True,
    )

# Sophiacord surface (agent identity / social graph)
def sophiacord_receipt(parcel_id, seller, buyer, settlement_tx_id) -> SurfaceReceipt:
    # Verify the agent identity record matches
    return SurfaceReceipt(
        surface="sophiacord",
        parcel_id=parcel_id,
        seller=seller,
        buyer=buyer,
        settlement_asset="RTC",
        settlement_tx_id=settlement_tx_id,
        settled=True,
    )
```

#### Coordinator Logic

The coordinator (initially the node authority; later a distributed coordinator)
collects receipts and builds the transfer event:

```python
def coordinate_transfer(
    parcel_id: str,
    seller: str,
    buyer: str,
    price_micrortc: int,
    settlement_tx_id: str,
    current_owners: dict[str, str],
) -> AtlasDeedTransfer:
    # Collect receipts from all surfaces (with timeout)
    receipts = collect_receipts(parcel_id, seller, buyer, settlement_tx_id,
                                timeout_seconds=30)

    # Build the transfer event (validates all receipts agree)
    transfer = build_atlas_deed_transfer(
        parcel_id=parcel_id,
        seller=seller,
        buyer=buyer,
        price_micrortc=price_micrortc,
        settlement_tx_id=settlement_tx_id,
        receipts=receipts,
    )

    # Apply to owner map (validates current ownership)
    new_owners = apply_deed_transfer(current_owners, transfer)

    # Phase 3: Push new owner map to all surfaces
    for surface in REQUIRED_SURFACES:
        push_owner_map(surface, new_owners, transfer.event_id)

    return transfer
```

#### Rollback Protocol

If any surface fails during Phase 3 (Commit or Verify):

```python
def rollback_transfer(transfer: AtlasDeedTransfer, previous_owners: dict[str, str]):
    """Revert all surfaces to the pre-transfer owner map."""
    for surface in REQUIRED_SURFACES:
        push_owner_map(surface, previous_owners, transfer.event_id)
    # Log the rollback for audit
    log_event("atlas_deed_transfer_rollback", transfer.event_id)
```

#### Split-Brain Handling

The reference implementation covers these edge cases:

1. **Partial surface receipts:** If only 2 of 3 surfaces respond within the
   timeout, the transfer is aborted. No owner map changes are made.
2. **Receipt conflict:** If any surface reports `settled=False` or disagrees on
   parcel_id/seller/buyer/settlement_tx_id, the transfer is aborted.
3. **Owner mismatch:** If `current_owner != transfer.previous_owner` at the time
   of application, the transfer is rejected (someone else transferred first).
4. **Tip-credit settlement attempts:** The protocol only accepts RTC settlement.
   Attempts to settle with Tip Credits are rejected at receipt validation.

#### Integration with Tip Maturation

Atlas deed transfers settle in RTC, not Tip Credits. However, tip maturation
settlements that fund RTC from `founder_community` can be used to purchase
Atlas deeds. The maturation checkpoint and deed transfer are independent
transactions — the deed transfer only requires that the buyer has settled RTC
in their balance, regardless of source.

---

## 6. Implementation Roadmap

| Phase | Component | Dependency | Estimated Effort |
|-------|-----------|------------|-----------------|
| 2a | Hybrid maturation checkpoint | Phase-1 ledger (exists) | 2–3 weeks |
| 2b | Beacon attestation binding | RIP-PoA (exists) | 1–2 weeks |
| 2c | Drain score computation | Phase-1 anti-abuse (exists) | 1 week |
| 2d | founder_community debit guard | lock_ledger.py (exists) | 1 week |
| 2e | Atlas deed atomicity | Reference impl (exists) | 2–3 weeks |

Total estimated: 7–10 weeks for Phase-2 completion.

---

## 7. Testing Strategy

Each component includes unit tests and integration tests:

1. **Maturation checkpoint:** Verify merkle root consistency, partial
   settlement on pool exhaustion, and reputation-only fallback.
2. **Attestation binding:** Verify one-to-one enforcement, epoch-bound
   validity, and burn-to-rebind flow.
3. **Drain score:** Verify composite scoring with synthetic patronage and
   sybil datasets; verify sliding window behavior.
4. **Debit guard:** Verify lock creation, 1-year unlock enforcement, and
   balance guard preventing overdrafts.
5. **Deed atomicity:** Use existing reference tests plus: timeout handling,
   rollback on partial failure, split-brain receipt detection.

---

*This guide is part of RIP-0301 Phase-2. Comment on the linked RFC issues or on
bottube.ai.*
