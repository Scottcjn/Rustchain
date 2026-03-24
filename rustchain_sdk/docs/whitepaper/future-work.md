# Future Work

This section summarizes extensions that are already referenced in the repo and ecosystem bounties, focusing on items that can be developed incrementally without destabilizing the core ledger and attestation plane.

## 1. Stronger, More Private Hardware Binding

Current binding logic makes pragmatic tradeoffs (e.g., incorporating source IP to reduce multi-wallet extraction). As the network grows, future work should improve:

- **Privacy**: minimize raw identifiers; prefer hashed or epoch-scoped derived signals.
- **Robustness under NAT**: avoid unfairly penalizing multiple legitimate miners behind one IP.
- **Portability**: allow legitimate hardware to migrate networks without losing identity, while still preventing “multi-wallet on one host”.

Potential direction: a server-issued binding token that is renewed periodically and tied to evidence-rich fingerprint checks.

## 2. Formalized Multiplier Schedule and Versioned Specs

The protocol benefits from transparent economics. Future work:

- Publish a versioned multiplier schedule (per architecture/family) and rationale.
- Add explicit protocol versioning to APIs and settlement rules so explorers can interpret historical data correctly.
- Provide a stable, “live-endpoint aligned” API reference to reduce drift in community docs and tooling.

## 3. Cross-Node Consistency and Auditability

As more nodes participate, the system needs stronger guarantees that nodes agree on:

- Epoch boundaries and settlement status
- Idempotency of settlement and internal transfers
- Synchronization of read surfaces used by explorers/clients

Future work includes cross-node validators, replay-protected replication of settlement decisions, and more explicit audit logs for chain mutation.

## 4. Ergo Anchoring Expansion (Proof-of-Existence)

Ergo anchoring is referenced as a way to make RustChain state tamper-evident by committing hashes externally. Future work:

- Define a stable commitment format (what is anchored, at what cadence).
- Add tooling to verify anchors against historical RustChain state.
- Make anchoring optional but easy for operators to enable.

## 5. GPU Render Marketplace / Compute Leasing

The ecosystem references a GPU marketplace where participants sell compute time for RTC. If pursued, it should be designed as a separate subsystem with clear boundaries:

- Avoid coupling marketplace escrow logic to core epoch settlement.
- Prefer signed, auditable job receipts and bounded queues.
- Add abuse controls: rate limiting, quotas, and dispute-handling hooks.

## 6. Ecosystem UX: Wallets, Explorer, and Museum

Network adoption depends on usable UX surfaces:

- Keep wallet flows safe (signed transfers, clear key handling, minimal privileged operations).
- Keep explorers aligned to real endpoints and bounded queries.
- Expand the hardware museum to better visualize “Proof-of-Antiquity” in a way that non-crypto users understand.

## 7. Developer Experience and Test Coverage

To keep security changes safe and reviewable:

- Add regression tests for critical flows: settlement, signed transfers, fingerprint validation, and rate limiting.
- Provide simple local dev harnesses (seed DB, deterministic epoch fixtures).
- Keep PRs focused: cosmetic changes separated from security-sensitive diffs.

