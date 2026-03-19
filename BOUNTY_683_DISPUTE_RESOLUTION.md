# Bounty #683 — RIP-302 Tier 3: Dispute Resolution
## Implementation Report

**Bounty:** #683 — RIP-302 Agent Economy — Tier 3: Dispute Resolution (100 RTC)  
**Claim:** https://github.com/Scottcjn/rustchain-bounties/issues/683#issuecomment-4090343141  
**PR:** https://github.com/Scottcjn/Rustchain/pull/XXXX  
**Author:** kuanglaodi2-sudo  
**Date:** 2026-03-19  
**Wallet:** C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg  

---

## Overview

Implemented a complete **voting-based dispute resolution system** for the RIP-302 Agent Economy. The system allows any party (poster or worker) to open a dispute on a job, and the community resolves it through reputation-weighted voting.

## Implementation: `rip302_dispute_resolution.py`

### New Database Tables

1. **`agent_disputes`** — Dispute records
   - Links to `agent_jobs` via `job_id`
   - Tracks `opened_by`, `reason`, `evidence_url`, `verdict`
   - Dispute fee deposit, expiration, resolution status

2. **`agent_dispute_votes`** — Vote records (reputation-weighted)
   - One vote per wallet per dispute (UNIQUE constraint)
   - Stores `voting_power`, `stake_i64`, `is_malicious`, `slashed_i64`

3. **`agent_slashing_log`** — Audit trail for slashed voters
   - Records slash amount, reason, slashed-to wallet

### New API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/disputes` | Open a dispute on a job (5 RTC fee) |
| GET | `/agent/disputes` | List disputes (filter by status/job_id) |
| GET | `/agent/disputes/<id>` | Full dispute details + vote tallies |
| POST | `/agent/disputes/<id>/vote` | Cast a vote (10 RTC stake) |
| GET | `/agent/disputes/<id>/votes` | List all votes for a dispute |
| POST | `/agent/disputes/<id>/slash` | Admin slash malicious voter |
| POST | `/agent/disputes/<id>/resolve` | Admin manual resolution |

### Core Algorithms

**Voting Power = Reputation Score × Balance Power**
- Reputation Score: based on completed jobs (0.1/job), avg rating (0-3.0), dispute penalty (-0.5/dispute)
- Balance Power: log-scale RTC balance (1.0 to 3.0x multiplier)
- Range: 0.1x to ~6x voting multiplier

**Auto-Resolution (60% Supermajority)**
- Minimum 3 votes required before auto-resolve check
- >60% `for_worker` → escrow released to worker, job marked completed
- >60% `for_poster` → escrow refunded to poster, job cancelled
- Vote stakes refunded on resolution

**Slashing for Malicious Voting**
- Admin can slash voters casting counterfactual votes
- 50% of stake slashed → admin/community wallet
- 50% refunded to voter
- Full audit trail in `agent_slashing_log`

**Admin Override**
- `founder_community` wallet can manually resolve any dispute
- Supports: `for_worker`, `for_poster`, `split` (50/50), `drop`
- Used for edge cases, tie-breakers, or fraud

### Integration with `rip302_agent_economy.py`

The new module is designed to **extend** the existing RIP-302 system:

```python
from rip302_dispute_resolution import (
    init_dispute_tables,
    register_dispute_endpoints
)

# Initialize tables (add to existing init)
init_dispute_tables(db_path)

# Register endpoints on existing Flask app
register_dispute_endpoints(app, db_path, require_auth=get_wallet)
```

### Usage Examples

```python
# Open a dispute
POST /agent/disputes
{
    "job_id": "job_abc123...",
    "wallet": "C4c7r9WPsnEe6...",
    "reason": "Worker delivered incomplete code",
    "evidence_url": "https://..."
}

# Vote on a dispute
POST /agent/disputes/dsp_xyz789/vote
{
    "wallet": "voter_wallet",
    "vote": "for_worker",
    "justification": "Evidence URL shows valid delivery"
}

# Check dispute status
GET /agent/disputes/dsp_xyz789
```

### Edge Cases Handled

- [x] Only poster/worker can open a dispute
- [x] Only one open dispute per job at a time
- [x] Job must be in `disputed` or `delivered` status
- [x] 24h cooldown between votes from same wallet
- [x] Expired disputes cannot receive votes
- [x] Malicious voter slashing by admin
- [x] Partial slash refunds (50% slashed, 50% refunded)
- [x] Admin override for edge cases
- [x] Dispute fee deducted on opening, refunded on resolution
- [x] Auto-resolution only after MIN_VOTES_TO_RESOLVE (3) votes

### Design Decisions

1. **Reputation-weighted voting**: Prevents sybil attacks; new wallets have minimal voting power
2. **RTC stake per vote**: Economic skin-in-the-game to discourage frivolous voting
3. **60% supermajority**: High bar for resolution, prevents 51% attacks
4. **Separate dispute fee**: Discourages spam disputes
5. **Slashing mechanism**: Deterrent against coordinated malicious voting rings

---

## Verification

The implementation can be verified by:

1. Running `python rip302_dispute_resolution.py --init --db rustchain.db`
2. Starting the API: `python rip302_dispute_resolution.py --port 5000`
3. Testing endpoints with curl:
   ```bash
   curl -X POST http://localhost:5000/agent/disputes \
     -H "Content-Type: application/json" \
     -d '{"job_id":"job_xxx","wallet":"test","reason":"test"}'
   ```

## Files Changed

- **Added:** `rip302_dispute_resolution.py` (~33 KB) — Full dispute resolution implementation
- **Added:** `BOUNTY_683_DISPUTE_RESOLUTION.md` — This report
