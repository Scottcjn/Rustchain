# Network Architecture and Security Analysis

This section documents RustChain's network architecture at a practical level (node roles, core services, and API surface), then outlines a security analysis focused on the threats the protocol explicitly targets: virtualization abuse, sybil-style reward extraction, replay/tampering on signed transfers, and operational attacks against public endpoints.

## Network Architecture

### Components

RustChain is implemented as a set of cooperating components:

- **Node (server)**: the primary HTTP service that exposes the public API, performs server-side validation, and maintains local state (SQLite DB).
- **Miners**: clients that periodically submit attestations and receive rewards based on weight/multiplier rules.
- **Explorer / Museum**: static web assets served by the node for network visibility; these consume read-only API endpoints.
- **Background operators** (optional): settlement automation, payout/ledger helpers, monitoring scripts.

### Node Roles and Trust Boundaries

RustChain differentiates operations by risk and gates sensitive operations with an admin key:

- **Public operations** (low trust): health checks, miner listing, epoch read endpoints, wallet balance queries by miner_id, signed transfer submission.
- **Sensitive operations** (high trust): settlement, internal/admin transfers, exporting full balance sets, and other chain-mutation workflows.

The admin key is intended to protect high-impact endpoints even if the public surface is rate-limited and validated.

### Data Plane vs Control Plane

Conceptually:

- **Data plane**: user/miner actions that should remain available without privileged secrets (e.g., attest submissions, signed transfers).
- **Control plane**: actions that can change global state or leak sensitive aggregated data (e.g., reward settlement, internal transfers).

RustChain enforces this separation using a combination of validation, rate limiting, and explicit admin-key checks.

### State Storage

The node stores state in SQLite tables, which typically include:

- Nonce/challenge tracking for attestations
- Miner balances
- Epoch state and settlement metadata
- Rate limiting tables
- Hardware binding records (anti multi-wallet)
- Optional audit tables (agent attestations/proofs, pending ledger)

This design favors operational simplicity and debuggability; it also means disk-growth and table bloat must be explicitly considered (see security section).

### Public API Surface (Representative)

While endpoints evolve, the public surface generally includes:

- `GET /health` for node health
- `GET /api/miners` for active miners and their device attributes
- `GET /epoch` for epoch metadata
- `GET /wallet/balance?miner_id=...` for balances
- `POST /attest/challenge` and `POST /attest/submit` for miner attestations
- `POST /wallet/transfer/signed` for Ed25519-signed user transfers

Explorer and museum web apps consume these endpoints read-only.

## Security Analysis

### Threats and Mitigations

#### 1. VM/Emulation Abuse (Cheap Scale)

**Threat**: attackers run many miners in VMs/containers to extract rewards cheaply, or spoof vintage architectures.

**Mitigations**:

- Hardware fingerprint checks with server-side evidence requirements for critical checks.
- Cross-validation of claimed architecture vs signals (e.g., SIMD identity).
- ROM fingerprint checks for known emulator signatures (where available).

Residual risk: sophisticated emulation can still mimic individual signals. RustChain's strategy is to layer multiple checks and keep raising the spoofing cost.

#### 2. Multi-Wallet Attacks from One Physical Host

**Threat**: a single machine attempts to earn multiple wallets' rewards.

**Mitigations**:

- Hardware binding logic that derives a server-observed `hardware_id` from IP + device properties and optional secondary entropy (MACs).
- Enforcement that one `hardware_id` maps to one miner identity (or rejection when conflicting).

Tradeoff: NAT/shared-IP environments can be noisy. The approach is operationally simple but may require tuning as the miner population grows.

#### 3. Abuse of Public Endpoints (Spam / DoS by State Growth)

**Threat**: attackers fill tables by spamming endpoints that create DB rows.

**Mitigations**:

- SQLite-backed per-IP rate limiting on attestation and similar endpoints.
- Prefer bounded queries and per-wallet caps for list endpoints.
- Admin-gating for high-impact state mutations.

Residual risk: even with rate limits, unbounded tables can grow if limits are too permissive. Periodic pruning/compaction is recommended for operational stability.

#### 4. Signed Transfer Tampering / Replay

**Threat**: attacker modifies a signed transfer payload or replays it.

**Mitigations**:

- Canonical JSON serialization for signing input (sorted keys, compact separators).
- Explicit inclusion of a nonce/timestamp field in signed payloads.
- Server-side verification of Ed25519 signatures before applying state changes.

Residual risk: any signature scheme depends on private key hygiene. Client tooling should enforce secure key storage (permissions, optional encryption).

#### 5. Privileged Endpoint Abuse (Control Plane Takeover)

**Threat**: attacker calls settlement/admin endpoints to mutate global state or exfiltrate aggregate data.

**Mitigations**:

- Mandatory admin key check for privileged endpoints.
- Clear separation of signed user transfers from internal/admin transfers.
- Operational hardening: keep admin key out of logs, restrict who can access the server environment.

Residual risk: compromise of the server host or its environment variables compromises the admin key; standard host hardening and secret management practices apply.

### Observability and Auditability

RustChain benefits from keeping state in transparent tables and emitting logs, but logs must not swallow errors. A secure configuration should:

- Log DB insert failures for audit tables (do not `except: pass` silently).
- Track rate-limit triggers and suspicious fingerprint failures.
- Keep sensitive values (keys, full identifiers) out of unauthenticated error responses.

### Recommendations (Low-Risk Improvements)

- Add explicit pruning strategies for high-write tables.
- Keep security-sensitive changes small and testable; prefer separate PRs for cosmetic changes.
- Publish a stable endpoint reference and keep explorer/museum consumers aligned with live endpoints.

