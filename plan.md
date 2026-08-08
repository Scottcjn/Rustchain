# Implementation Plan: RIP-310 Social Mining Protocol (#2239)

## 1. Architecture Design & System Design Trade-Offs

### 1.1 Tipping & Treasury Fee Model
- **Mechanism**: Dynamic fee deduction engine for P2P tips.
- **Inflow**: 8% platform fee subtracted on each tip, deposited directly to `social_mining_pool`.
- **Identity Enforcement**: Both tipper and recipient require valid Beacon IDs (Hardware Attested).

### 1.2 Reward Engine & Frequency Capping
- **Reward Distributer**: Calculates daily activity payouts (Moltbook 0.01 RTC, 4claw 0.01 RTC, BoTTube 0.05 RTC, Comment 0.002 RTC, Upvote 0.001 RTC).
- **Anti-Gaming (RIP-309)**: Nonce rotation selects active metrics per epoch to prevent sybil/bot farming.

### 1.3 System Design Trade-Offs (Reference: system-design-primer)
- **Consistency vs. Availability (CAP Theorem)**:
  - Tipping transactions prioritize strong consistency over immediate availability to prevent double-spending social mining treasury pools.
- **In-Memory Ledger State vs. Disk Persistence**:
  - Pool ledger uses atomic in-memory balances backed by transaction logs for sub-second micro-tip throughput while keeping full auditability.

## 2. Impact Assessment & Scope
- **New Files**:
  - `rip310_social_mining.py` (Core implementation)
  - `tests/test_rip310_social_mining.py` (Unit tests with pytest)
- **Zero Impact Files**: Engine, node, and core chain consensus files remain unchanged.

## 3. Verification Plan
- Automated TDD pytest suite: `pytest tests/test_rip310_social_mining.py`
- Target test coverage: ≥80%
