# RIP-202: Fail-Closed Producer Enrollment Gate

**Status**: Draft (2026-05-31)
**Author**: Scott Boudreaux (Elyan Labs)
**Reviewers**: Tri-brain (Claude Opus 4.8 · Codex 5.5 · Grok)
**Type**: Consensus Security
**Requires**: RIP-200 (Round-Robin Consensus), RIP-201 (Fleet Immune System)

## Abstract

The block-producer enrollment gate added to `rustchain_block_producer.py` currently **fails open**: a miner with no `epoch_enroll` row for the epoch receives a heuristic producer weight, so an unenrolled or VM/emulator miner can regain producer duties simply by *never enrolling*. Only an explicit `weight <= 0` row excludes. RIP-202 makes the gate **fail-closed** — a miner absent from a *finalized* enrollment snapshot is excluded from producer rotation — while guaranteeing **no chain fork** via a deterministic epoch-height activation gate and a deterministic enrollment-finalized signal.

## Motivation

Producer selection (`get_round_robin_producer` → `_build_balanced_producer_rotation` → `rotation[slot % len]`) is **deterministic consensus**: every honest node must select the same producer for each slot, or the chain forks. Two facts make the current gate unsafe to "just fix":

1. **It fails open.** `enroll_weights.get(miner, None)` → absent miners fall through to the device heuristic. The anti-VM enrollment gate (RIP-201 fleet immune system) can *exclude* a flagged miner (explicit weight 0) but cannot *require* enrollment. Threat: an emulated/Sybil miner skips enrollment entirely and keeps producer eligibility.
2. **Any naive fix forks the chain.** Changing the eligible set or weights changes the deterministic selection output. If nodes upgrade piecemeal, upgraded and un-upgraded nodes pick different producers at the same slot → fork. And using "rows exist for the epoch" as the activation marker is unsound — it flips true on the *first* ingested row, so partial/phased enrollment ingestion silently drops not-yet-ingested honest miners.

RIP-202 closes the gate with the minimum possible consensus delta and a coordinated activation.

## Specification

### 1. Activation gate (atomic fleet-wide switch)

A consensus constant ships in the node binary:

```python
# Epoch at/after which the fail-closed producer enrollment gate is enforced.
# MUST be set far enough in the future that the whole fleet upgrades first.
RIP0202_ACTIVATION_EPOCH = <chosen_future_epoch>
```

- `epoch < RIP0202_ACTIVATION_EPOCH` → **behavior is byte-for-byte identical to today** (fail-open heuristic). This guarantees historical blocks replay identically — no retroactive fork.
- `epoch >= RIP0202_ACTIVATION_EPOCH` → fail-closed rule (§3) applies, but **only when enrollment for that epoch is finalized** (§2).

Because the constant is in the binary and keyed to epoch (a deterministic function of chain height), every node running the RIP-202 build flips at the same epoch. Rollout = upgrade the fleet before `RIP0202_ACTIVATION_EPOCH`.

### 2. Authoritative "enrollment finalized" signal

A miner being *absent* may mean "excluded" or "snapshot still ingesting." We need an authoritative, **deterministic** marker that epoch E's enrollment is complete. RIP-202 introduces:

```sql
CREATE TABLE IF NOT EXISTS epoch_enroll_state (
    epoch          INTEGER PRIMARY KEY,
    finalized      INTEGER NOT NULL DEFAULT 0,   -- 1 once the snapshot is sealed
    snapshot_hash  TEXT,                          -- hash of the sorted enrolled set
    finalized_at   INTEGER                        -- chain-derived, NOT wall clock
);
```

- The epoch-settlement step (the same deterministic process that computes `epoch_rewards` / `epoch_enroll`) seals epoch E's enrollment by inserting `finalized=1` **as a deterministic function of chain state** (e.g. once the chain height passes E's enrollment-snapshot boundary). It MUST NOT depend on local wall-clock or node-local timing, or finalization itself would diverge.
- `_enrollment_finalized(conn, epoch)` returns True iff a `finalized=1` row exists for that epoch.

The gate is enforced for epoch E only when `epoch >= ACTIVATION AND _enrollment_finalized(E)`. A first-ingested-row can no longer trip it.

### 3. Fail-closed rule (post-activation, epoch finalized)

`get_attested_miners` sets, for each attested miner:

```python
gate_active = (epoch >= RIP0202_ACTIVATION_EPOCH) and _enrollment_finalized(conn, epoch)
enroll_weight = enroll_weights.get(miner, 0 if gate_active else None)
```

`_miner_selection_weight`:

| `enroll_weight` | meaning | result |
|---|---|---|
| `None` | pre-activation, or no finalized snapshot (bootstrap) | **heuristic** (existing behavior — liveness) |
| `<= 0` | flagged (VM/emulator) **or** absent from a finalized snapshot | **0.0 — excluded** |
| `> 0` | enrolled | **eligible — keep the existing heuristic weight** |
| malformed (non-numeric) | corrupt row | **0.0 — fail closed** |

### 4. Scope decision (no creep)

RIP-202 changes **eligibility only**, not weight distribution. A `> 0` enroll_weight marks a miner *eligible* and then falls through to the existing device heuristic; RIP-202 deliberately **does NOT** make `enroll_weight` the authoritative selection weight. Making enrolled weights authoritative-over-heuristic is a separate consensus-weighting change, deferred to a future **RIP-203**. This keeps the activation-boundary consensus delta to the single, auditable change "unenrolled-when-finalized miners drop from rotation."

### 5. Bootstrap / liveness

- Before `RIP0202_ACTIVATION_EPOCH`: unchanged.
- After activation but no finalized snapshot for the epoch (settlement lag, early rollout, genuine genesis bootstrap): fall back to heuristic → **the chain never halts** for lack of enrollment data.
- Missing `epoch_enroll` / `epoch_enroll_state` table is treated as "not finalized" → heuristic (test/bootstrap safe). The broad `OperationalError` catch is narrowed to the missing-table case so schema corruption does not silently fail open.

## Rollout

1. Ship the RIP-202 build with `RIP0202_ACTIVATION_EPOCH = current_epoch + N` (N chosen to cover fleet-upgrade time).
2. Confirm epoch settlement writes `epoch_enroll_state.finalized=1` deterministically for each new epoch.
3. Monitor: every node reports the same `snapshot_hash` per finalized epoch (divergence alarm).
4. At `RIP0202_ACTIVATION_EPOCH`, fail-closed enforcement begins fleet-wide simultaneously.

## Test Plan (must pass before activation)

- **Determinism**: identical `(epoch, finalized enroll snapshot, attested set)` → byte-identical `_build_balanced_producer_rotation` across independent nodes.
- **No retroactive fork**: for every `epoch < ACTIVATION`, new build produces the *same* producer sequence as the old build (replay historical slots).
- **Fail-closed**: with finalized enrollment, an attested-but-absent miner gets weight 0 and never appears in the rotation.
- **Bootstrap liveness**: activation reached but no finalized snapshot → rotation falls back to heuristic, chain advances.
- **Malformed/zero**: corrupt or `<=0` weight → excluded, no crash.
- **Mixed-version boundary**: a node upgraded early (still pre-activation epoch) selects identically to an un-upgraded node, proving the gate is dormant until the activation epoch.

## Security Considerations

The activation gate and the enrollment-finalized marker MUST both be deterministic functions of chain state. If either depends on node-local timing, finalization or activation could diverge and *cause* the fork this RIP exists to prevent. The `snapshot_hash` divergence monitor (Rollout §3) is the tripwire.

## Backwards Compatibility

Fully backwards compatible until `RIP0202_ACTIVATION_EPOCH`. Pre-activation replay is identical. Post-activation, the only behavioral change is exclusion of miners absent from a finalized enrollment snapshot — the intended fix.

---

## Normative Invariants (from tri-brain review — Codex 5.5 + Grok, 4 rounds)

The review established that producer selection is **deterministic consensus**, so the fix is only safe if the data it reads is itself deterministic across the fleet. The producer module *cannot* enforce this alone — these are protocol/settlement obligations that MUST hold before `RIP0202_ACTIVATION_EPOCH` is set to a concrete value:

- **INV-1 (deterministic inputs).** `epoch_enroll`, `epoch_enroll_state`, and `miner_attest_recent` MUST be deterministic functions of finalized chain state — byte-identical on every honest node for a given epoch. (This is a *pre-existing* precondition of the current selector, which already reads these tables; RIP-202 makes it load-bearing for exclusion.) No selection decision may depend on node-local DB state, timing, or TTL view.
- **INV-2 (no empty finalization).** Epoch settlement MUST NOT write `finalized=1` for an epoch whose eligible set is empty or all-≤0. A finalized snapshot always contains ≥1 eligible producer. This replaces a node-local "all-excluded → heuristic" backstop (rejected: it decides from the local attested set → fork) — liveness is guaranteed by settlement, not by the producer.
- **INV-3 (finalize before use).** The `finalized=1` marker for epoch E MUST be written (deterministically, as a function of chain height) *before* any slot in E selects a producer, so the gate cannot flip mid-epoch.
- **INV-4 (atomic activation).** Every honest node MUST run a build whose `RIP0202_ACTIVATION_EPOCH` is the same value before that epoch. A source constant has no technical atomicity; a skewed rollout forks at the boundary. *Recommended hardening:* migrate activation to an **on-chain governance height** so activation is read from chain state, not the binary.
- **INV-5 (read-fault stance — OPEN DECISION).** If, post-activation, the required chain-derived enrollment data is genuinely unreadable on a node, every local choice (heuristic fallback vs all-excluded) diverges from nodes that read successfully. The only consistent options are (a) INV-1 guarantees the data is always present so this never occurs, or (b) an unreadable read is a **deterministic halt/refuse-to-produce fault** for that node. This is a protocol stance, not a code default — see Open Decisions.

## Decisions (operator, 2026-05-31)

1. **Activation mechanism — DECIDED: on-chain governance activation height** (robust). Activation is read from chain-replicated governance state, not a binary constant, so it flips atomically fleet-wide (eliminates the INV-4 rollout-skew fork). *More work — see PREREQ-A.*
2. **INV-5 read-fault stance — DECIDED: rely on INV-1 (data always present).** No node-local halt/heuristic fallback on missing post-activation data: INV-1 guarantees the deterministic snapshot exists, so the missing-data path is bootstrap-only (pre-activation) and therefore uniformly heuristic across the fleet.

## Prerequisites (discovered by codebase grounding 2026-05-31 — must land BEFORE activation)

Both decisions require consensus infrastructure that **does not exist yet**. RIP-202's producer-side change is the *last* step, not the first.

- **PREREQ-A — deterministic, chain-replicated governance parameters.** `node/governance.py` today only *stores and votes on* proposals: there is **no `governance_params` table, no proposal execution, and no cross-node synchronization** (each node has a local SQLite governance DB). Before activation-by-governance-height is meaningful we must build: (1) a `governance_params` table that is deterministic chain-derived state, (2) execution of a passed `parameter_change` proposal into it, (3) a runtime `get_param(name)` read, and (4) replication so every node reads the identical activation height. Until then, reading activation from governance would itself be node-local → fork.
- **PREREQ-B — deterministic, chain-replicated enrollment snapshot (INV-1/2/3).** `epoch_enroll` is currently written per-attestation in `_submit_attestation_impl` (`POST /attest/submit`) from node-local `miner_attest_recent`, with weight `HARDWARE_WEIGHTS[family][arch]` (0 for failed fingerprint). It is an *audit snapshot*, not consensus state, and is **not** used for reward distribution (settlement reads `miner_attest_recent`). For INV-1 the epoch-settlement step (`rewards_implementation_rip200.settle_epoch_rip200`) must, at a deterministic chain height, **seal** the epoch's enrollment into an `epoch_enroll_state(epoch, finalized, snapshot_hash, ...)` row computed deterministically from chain-replicated attestation data, enforce INV-2 (never seal an empty/all-≤0 set), and satisfy INV-3 (seal before any slot in the epoch selects a producer).

## Implementation order (revised)

1. **PREREQ-A**: governance param substrate (`governance_params` + execution + `get_param` + replication).
2. **PREREQ-B**: deterministic enrollment snapshot + `epoch_enroll_state` finalization in settlement (INV-1/2/3).
3. **Producer gate** (this module): read activation height via `get_param("rip0202_activation_epoch")` instead of a source constant; engage the fail-closed gate. *(Drafted, dormant, tri-brain-reviewed — ready to wire to `get_param` once PREREQ-A exists.)*
4. **Activation**: a governance proposal sets the activation height to a future epoch after the fleet runs the build.

## Implementation status

The producer-side change (`node/rustchain_block_producer.py`) is drafted and tri-brain-reviewed to a **minimal deterministic core**, shipping **dormant** (`RIP0202_ACTIVATION_EPOCH = None`, byte-identical behavior). It is intentionally **NOT** merged or activated: activation is unsafe until INV-1..3 are implemented in settlement and Decisions 1–2 are made. Tests for the gate paths are pending the activation-mechanism decision (the test fixtures depend on it).
