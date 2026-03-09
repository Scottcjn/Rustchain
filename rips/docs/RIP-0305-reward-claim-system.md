# RIP-305: Reward Claim System & Eligibility Flow
**Title:** Reward Claim Page and Eligibility Verification System  
**Author:** Scott Boudreaux (Elyan Labs)  
**Status:** Draft  
**Type:** Standards Track  
**Category:** Core  
**Created:** 2026-03-09  
**Requires:** RIP-0001, RIP-0200, RIP-0201  
**License:** Apache 2.0  

---

## Track D: Claim Page + Eligibility Flow

This document specifies **Track D** of RIP-305: a comprehensive reward claim system with real-time eligibility verification, web-based claim interface, and on-chain settlement integration.

# Summary

RIP-305 Track D delivers a production-ready reward claim system for RustChain miners, comprising:

1. **Eligibility Verification API** — Real-time endpoint for miners to check reward eligibility
2. **Web Claim Interface** — User-friendly HTML/CSS/JS claim page with wallet integration
3. **Claims Database** — Persistent tracking of claim requests, status, and settlement
4. **Anti-Fraud Measures** — Signature verification, rate limiting, and duplicate prevention
5. **Settlement Integration** — Direct integration with epoch reward settlement (RIP-0200)

# Abstract

Miners who participate in RustChain's Proof of Antiquity consensus earn RTC rewards through epoch-based distribution (RIP-0200). RIP-305 Track D provides the complete infrastructure for miners to:

- **Verify eligibility** before claiming (attestation status, epoch participation, fingerprint validation)
- **Submit claim requests** through a secure web interface or API
- **Track claim status** from submission through settlement
- **Receive rewards** via on-chain transfer to verified wallet addresses

The system is designed for:
- **Real hardware only** — Integrates with RIP-0007 entropy fingerprinting and RIP-0201 fleet detection
- **Self-custody** — Miners control their own wallets; no custodial risk
- **Transparency** — All claims are publicly auditable via the claims ledger
- **Automation-friendly** — RESTful API for programmatic claim submission

# Motivation

## Why a Claim System?

While RIP-0200 defines epoch reward calculation, it does not specify how miners actually **receive** their rewards. Prior to RIP-305:

1. **No standardized claim flow** — Miners had no clear path to request earned rewards
2. **Manual processes** — Reward distribution required manual intervention
3. **No visibility** — Miners couldn't track claim status or history
4. **Fraud risk** — Lack of signature verification and duplicate detection

## Design Goals

- **Simplicity**: A miner should be able to claim rewards in under 2 minutes
- **Security**: Cryptographic proof of ownership, no API keys or passwords
- **Transparency**: Public claims ledger for community auditing
- **Automation**: API-first design for bots and monitoring tools
- **Compliance**: Rate limiting, fraud detection, and audit trails

# Specification

## 1. Eligibility Verification

### 1.1 Eligibility Criteria

A miner is eligible to claim rewards if ALL conditions are met:

| Criterion | Description | Source |
|-----------|-------------|--------|
| **Attestation Valid** | Current attestation within TTL (24 hours) | `miner_attest_recent` |
| **Epoch Participation** | Attested during at least one slot in the epoch | `miner_attest_recent` history |
| **Fingerprint Passed** | Hardware fingerprint validation succeeded | `fingerprint_passed = 1` |
| **No Fleet Penalty** | Not flagged as part of a suspicious fleet | RIP-0201 fleet detection |
| **Wallet Registered** | Valid wallet address on file | `miner_wallets` table |
| **No Pending Claim** | No existing unprocessed claim for same epoch | `claims` table |

### 1.2 Eligibility API Endpoint

```
GET /api/claims/eligibility?miner_id=<MINER_ID>&epoch=<EPOCH_NUMBER>
```

**Response (200 OK):**
```json
{
  "eligible": true,
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "reward_urtc": 1500000,
  "reward_rtc": 0.015,
  "wallet_address": "RTC1abc123...",
  "attestation": {
    "last_seen_slot": 175680,
    "last_seen_ts": 1741564800,
    "device_arch": "n64_mips",
    "antiquity_multiplier": 2.5
  },
  "fingerprint": {
    "passed": true,
    "entropy_score": 0.075
  },
  "fleet_status": {
    "bucket": "retro_console",
    "fleet_size": 3,
    "penalty_applied": false
  },
  "checks": {
    "attestation_valid": true,
    "epoch_participation": true,
    "fingerprint_passed": true,
    "wallet_registered": true,
    "no_pending_claim": true
  },
  "reason": null
}
```

**Response (400 Bad Request - Not Eligible):**
```json
{
  "eligible": false,
  "miner_id": "fake-miner-123",
  "epoch": 1234,
  "reward_urtc": 0,
  "reason": "not_attested",
  "checks": {
    "attestation_valid": false,
    "epoch_participation": false,
    "fingerprint_passed": null,
    "wallet_registered": false,
    "no_pending_claim": true
  }
}
```

### 1.3 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `not_attested` | 400 | Miner has no valid attestation within TTL |
| `no_epoch_participation` | 400 | Miner was not attested during the specified epoch |
| `fingerprint_failed` | 400 | Hardware fingerprint validation failed |
| `wallet_not_registered` | 400 | No wallet address registered for this miner |
| `pending_claim_exists` | 409 | Unprocessed claim already exists for this epoch |
| `epoch_not_settled` | 400 | Epoch has not been settled yet |
| `invalid_miner_id` | 400 | Miner ID format is invalid or not found |
| `rate_limited` | 429 | Too many requests (max 10/minute per miner) |

## 2. Claim Submission

### 2.1 Claim Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    MINER     │     │   WEB UI     │     │   NODE API   │
│              │     │              │     │              │
│  1. Check    │────►│  2. Render   │     │              │
│  eligibility │     │  claim form  │     │              │
│              │     │              │     │              │
│              │     │  3. Submit   │────►│  4. Validate │
│              │     │  claim       │     │  signature   │
│              │     │              │     │              │
│              │     │              │     │  5. Create   │
│              │     │              │◄────│  claim record│
│              │     │              │     │              │
│  6. Poll     │────►│  7. Display  │     │              │
│  status      │     │  status      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 2.2 Claim Submission API

```
POST /api/claims/submit
Content-Type: application/json

{
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "wallet_address": "RTC1abc123...",
  "signature": "<Ed25519 signature of claim payload>",
  "public_key": "<Ed25519 public key for verification>"
}
```

**Signature Payload:**
The signature is computed over the canonical JSON representation of:
```json
{
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "wallet_address": "RTC1abc123...",
  "timestamp": 1741564800
}
```

**Response (201 Created):**
```json
{
  "claim_id": "claim_1234_n64-scott-unit1",
  "status": "pending",
  "submitted_at": "2026-03-09T12:00:00Z",
  "estimated_settlement": "2026-03-09T12:30:00Z",
  "reward_urtc": 1500000,
  "reward_rtc": 0.015
}
```

### 2.3 Claim Status API

```
GET /api/claims/status/<CLAIM_ID>
```

**Response:**
```json
{
  "claim_id": "claim_1234_n64-scott-unit1",
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "status": "settled",
  "submitted_at": "2026-03-09T12:00:00Z",
  "settled_at": "2026-03-09T12:28:45Z",
  "reward_urtc": 1500000,
  "reward_rtc": 0.015,
  "wallet_address": "RTC1abc123...",
  "transaction_hash": "0xabc123def456...",
  "settlement_batch": "batch_2026_03_09_001"
}
```

**Status Values:**
- `pending` — Claim submitted, awaiting verification
- `verifying` — Undergoing fraud/fleet checks
- `approved` — Verified, queued for settlement
- `settled` — Reward transferred to wallet
- `rejected` — Claim denied (reason provided)
- `failed` — Settlement transaction failed (retry scheduled)

## 3. Database Schema

### 3.1 Claims Table

```sql
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    miner_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    wallet_address TEXT NOT NULL,
    reward_urtc INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at INTEGER NOT NULL,
    verified_at INTEGER,
    settled_at INTEGER,
    transaction_hash TEXT,
    settlement_batch TEXT,
    rejection_reason TEXT,
    signature TEXT NOT NULL,
    public_key TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(miner_id, epoch)
);

CREATE INDEX IF NOT EXISTS idx_claims_miner ON claims(miner_id);
CREATE INDEX IF NOT EXISTS idx_claims_epoch ON claims(epoch);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_submitted ON claims(submitted_at);
```

### 3.2 Claim Audit Log

```sql
CREATE TABLE IF NOT EXISTS claims_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT,
    details TEXT,
    timestamp INTEGER NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_audit_claim ON claims_audit(claim_id);
```

## 4. Security Considerations

### 4.1 Signature Verification

All claims MUST be signed with the miner's Ed25519 private key. The node verifies:
- Signature validity against the provided public key
- Public key matches the one registered with the miner (if applicable)
- Timestamp is within acceptable window (±5 minutes)

### 4.2 Rate Limiting

To prevent abuse:
- **Eligibility checks**: Max 10 requests per minute per miner_id
- **Claim submissions**: Max 3 requests per minute per miner_id
- **Status checks**: Max 30 requests per minute per IP

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1741564860
```

### 4.3 Duplicate Prevention

The `UNIQUE(miner_id, epoch)` constraint prevents duplicate claims for the same epoch. Attempting to submit a duplicate returns HTTP 409 Conflict.

### 4.4 Fraud Detection

Integration with RIP-0201 fleet detection:
- Claims from miners in flagged fleets are held for manual review
- Correlated claims (same IP, similar timestamps) trigger additional scrutiny
- Unusual claim patterns (e.g., sudden wallet address changes) are logged

## 5. Web Claim Interface

### 5.1 Claim Page Features

The web-based claim interface (`/claims`) provides:

1. **Miner ID Input** — Enter or paste miner ID
2. **Eligibility Check** — Real-time verification with visual feedback
3. **Epoch Selection** — Dropdown of settled epochs with pending rewards
4. **Wallet Address Entry** — With validation for RTC address format
5. **Claim Submission** — One-click claim with signature generation
6. **Status Dashboard** — Live updates on claim progress
7. **Claim History** — Table of past claims with export to CSV

### 5.2 UI/UX Requirements

- **Responsive Design** — Mobile-friendly layout
- **Accessibility** — WCAG 2.1 AA compliance (ARIA labels, keyboard navigation)
- **Error Handling** — Clear, actionable error messages
- **Loading States** — Spinners/skeletons during async operations
- **Confirmation** — Explicit confirmation before submitting claims

### 5.3 Wallet Integration

For miners without a wallet:
- Link to official RustChain wallet download
- QR code for mobile wallet apps
- Instructions for generating a new address

For miners with existing wallets:
- Auto-detect registered wallet address
- Option to update wallet address (requires re-signature)

## 6. Settlement Integration

### 6.1 Batch Settlement

Claims are settled in batches to optimize transaction fees:
- **Batch window**: Every 30 minutes (configurable)
- **Minimum batch size**: 10 claims OR 30 minutes elapsed
- **Maximum batch size**: 100 claims per batch

### 6.2 Settlement Process

1. **Claim Aggregation** — Collect all `approved` claims
2. **Balance Check** — Verify sufficient rewards pool balance
3. **Transaction Construction** — Build multi-output transaction
4. **Signing** — Sign with node's treasury key
5. **Broadcast** — Submit to RustChain network
6. **Confirmation** — Wait for block inclusion
7. **Status Update** — Mark claims as `settled` with tx hash

### 6.3 Failure Handling

If a settlement transaction fails:
- **Retry logic**: Up to 3 automatic retries with exponential backoff
- **Alert**: Notify operators after 3 failures
- **Manual review**: Claims flagged for operator intervention

# Reference Implementation

## Files Created

1. **`rips/docs/RIP-0305-reward-claim-system.md`** — This specification
2. **`node/claims_eligibility.py`** — Eligibility verification logic
3. **`node/claims_submission.py`** — Claim submission and validation
4. **`node/claims_settlement.py`** — Batch settlement processor
5. **`web/claims/index.html`** — Claim page UI
6. **`web/claims/claims.css`** — Claim page styles
7. **`web/claims/claims.js`** — Claim page client logic
8. **`tests/test_claims_eligibility.py`** — Unit tests for eligibility
9. **`tests/test_claims_submission.py`** — Unit tests for submission
10. **`tests/test_claims_integration.py`** — End-to-end integration tests
11. **`docs/CLAIMS_GUIDE.md`** — User documentation

## Files Modified

1. **`node/rustchain_v2_integrated_v2.2.1_rip200.py`** — Add claims API routes
2. **`node/rewards_implementation_rip200.py`** — Integrate with settlement
3. **`rips/python/rustchain/fleet_immune_system.py`** — Fleet check integration

# Acknowledgments

- **RIP-0001** (Sophia Core Team) — Proof of Antiquity consensus foundation
- **RIP-0200** — 1 CPU = 1 Vote round-robin consensus and epoch rewards
- **RIP-0201** — Fleet Detection Immune System
- **RustChain Wallet Team** — Wallet address format and signing libraries

# Copyright

This document is licensed under Apache License, Version 2.0.
