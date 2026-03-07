# RustChain Bounty Claims System

## Overview

The Bounty Claims System provides a complete integration path for submitting, tracking, and managing bounty claims within the RustChain ecosystem. This system ties directly into the existing RustChain node infrastructure, using real endpoints and database persistence.

**Key Features:**
- Submit claims for active bounties (MS-DOS Validator, Classic Mac OS, etc.)
- Track claim status through review workflow
- Admin approval/rejection workflow with reward distribution
- Public API for claim verification
- Integration with RustChain miner identities

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Claimant      │────▶│  RustChain Node  │────▶│  SQLite Database│
│   (Miner)       │     │  (Flask API)     │     │  (Persistence)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Admin Dashboard │
                        │  (Review/Pay)    │
                        └──────────────────┘
```

## Available Bounties

| Bounty ID | Title | Reward | Status |
|-----------|-------|--------|--------|
| `bounty_dos_port` | MS-DOS Validator Port | Uber Dev Badge + RUST 500 | Open |
| `bounty_macos_75` | Classic Mac OS 7.5.x Validator | Uber Dev Badge + RUST 750 | Open |
| `bounty_win31_progman` | Win3.1 Progman Validator | Uber Dev Badge + RUST 600 | Open |
| `bounty_beos_tracker` | BeOS / Haiku Native Validator | Uber Dev Badge + RUST 400 | Open |
| `bounty_web_explorer` | RustChain Web Explorer | Uber Dev Badge + RUST 1000 | Open |
| `bounty_relic_lore_scribe` | Relic Lore Scribe | Flamekeeper Lore Badge + RUST 350 | Open |

## API Endpoints

### Public Endpoints

#### List Available Bounties
```http
GET /api/bounty/list
```

Returns all available bounties with claim statistics.

**Response:**
```json
{
  "bounties": [
    {
      "bounty_id": "bounty_dos_port",
      "title": "MS-DOS Validator Port",
      "description": "Create a RustChain validator client that runs on real-mode DOS.",
      "reward": "Uber Dev Badge + RUST 500",
      "status": "Open",
      "claim_count": 5,
      "pending_claims": 2
    }
  ],
  "count": 6
}
```

#### Get Claim Details
```http
GET /api/bounty/claims/<claim_id>
```

Returns details of a specific claim (public view, sensitive data redacted).

**Response:**
```json
{
  "claim_id": "CLM-ABC123DEF456",
  "bounty_id": "bounty_dos_port",
  "claimant_miner_id": "RTC_test...",
  "submission_ts": 1740783600,
  "status": "under_review",
  "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
  "reward_amount_rtc": 500.0,
  "reward_paid": 0
}
```

#### Get Miner's Claims
```http
GET /api/bounty/claims/miner/<miner_id>?limit=50
```

Returns all claims submitted by a specific miner.

**Response:**
```json
{
  "miner_id": "RTC_test_miner",
  "claims": [
    {
      "claim_id": "CLM-111",
      "bounty_id": "bounty_dos_port",
      "submission_ts": 1740783600,
      "status": "approved",
      "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
      "reward_amount_rtc": 500.0,
      "reward_paid": 1
    }
  ],
  "count": 1
}
```

#### Get Bounty Statistics
```http
GET /api/bounty/statistics
```

Returns aggregate statistics for all bounty claims.

**Response:**
```json
{
  "total_claims": 25,
  "status_breakdown": {
    "pending": 10,
    "approved": 8,
    "rejected": 5,
    "under_review": 2
  },
  "total_rewards_paid_rtc": 4500.0,
  "by_bounty": {
    "bounty_dos_port": {
      "pending": 3,
      "approved": 2
    }
  }
}
```

### Admin Endpoints (Require X-Admin-Key)

#### Submit Claim
```http
POST /api/bounty/claims
Content-Type: application/json
```

**Request Body:**
```json
{
  "bounty_id": "bounty_dos_port",
  "claimant_miner_id": "RTC_wallet_address",
  "description": "Completed MS-DOS validator with BIOS date entropy and FAT filesystem output.",
  "claimant_pubkey": "ed25519_pubkey_hex",
  "github_pr_url": "https://github.com/user/rustchain-dos/pull/1",
  "github_repo": "user/rustchain-dos",
  "commit_hash": "abc123def456",
  "evidence_urls": [
    "https://github.com/user/rustchain-dos",
    "https://example.com/demo.mp4"
  ]
}
```

**Required Fields:**
- `bounty_id`: Must be one of the valid bounty IDs
- `claimant_miner_id`: Miner wallet address (1-128 chars)
- `description`: Claim description (1-5000 chars)

**Optional Fields:**
- `claimant_pubkey`: Miner's public key
- `github_pr_url`: GitHub pull request URL
- `github_repo`: GitHub repository name
- `commit_hash`: Git commit hash (7 or 40 hex chars)
- `evidence_urls`: List of evidence URLs

**Response (201 Created):**
```json
{
  "claim_id": "CLM-ABC123DEF456",
  "bounty_id": "bounty_dos_port",
  "status": "pending",
  "submitted_at": 1740783600,
  "message": "Claim submitted successfully"
}
```

#### Get Claims by Bounty (Admin Only)
```http
GET /api/bounty/claims/bounty/<bounty_id>?status=pending
```

Returns all claims for a specific bounty (admin view with full details).

#### Update Claim Status (Admin Only)
```http
PUT /api/bounty/claims/<claim_id>/status
Content-Type: application/json
X-Admin-Key: <admin_key>
```

**Request Body:**
```json
{
  "status": "approved",
  "reviewer_notes": "Excellent work! All requirements met.",
  "reward_amount_rtc": 500.0
}
```

**Valid Status Values:**
- `pending`: Initial state
- `under_review`: Being reviewed
- `approved`: Approved for payment
- `rejected`: Rejected

**Response:**
```json
{
  "claim_id": "CLM-ABC123DEF456",
  "status": "approved",
  "updated_at": 1740783600,
  "message": "Claim status updated to approved"
}
```

#### Mark Claim as Paid (Admin Only)
```http
POST /api/bounty/claims/<claim_id>/pay
Content-Type: application/json
X-Admin-Key: <admin_key>
```

**Request Body:**
```json
{
  "payment_tx_id": "tx_abc123def456"
}
```

**Response:**
```json
{
  "claim_id": "CLM-ABC123DEF456",
  "paid": true,
  "payment_tx_id": "tx_abc123def456",
  "paid_at": 1740783600
}
```

## Python SDK Usage

### Installation

```bash
pip install rustchain-sdk
```

### Quick Start

```python
from rustchain import RustChainClient, BountyError

# Initialize client
client = RustChainClient("https://rustchain.org", verify_ssl=False)

# List available bounties
bounties = client.list_bounties()
for bounty in bounties:
    print(f"{bounty['title']}: {bounty['reward']}")

# Submit a claim
try:
    result = client.submit_bounty_claim(
        bounty_id="bounty_dos_port",
        claimant_miner_id="RTC_wallet_address",
        description="Completed MS-DOS validator with BIOS entropy",
        github_pr_url="https://github.com/user/rustchain-dos/pull/1",
        evidence_urls=["https://example.com/demo.mp4"]
    )
    print(f"Claim submitted: {result['claim_id']}")
except BountyError as e:
    print(f"Claim failed: {e}")

# Check claim status
claim = client.get_bounty_claim("CLM-ABC123DEF456")
print(f"Status: {claim['status']}")

# Get all claims for a miner
claims = client.get_miner_bounty_claims("RTC_wallet_address")
for claim in claims:
    print(f"{claim['claim_id']}: {claim['status']}")

# Get statistics
stats = client.get_bounty_statistics()
print(f"Total claims: {stats['total_claims']}")
print(f"Rewards paid: {stats['total_rewards_paid_rtc']} RTC")

client.close()
```

### Error Handling

```python
from rustchain import BountyError
from rustchain.exceptions import ValidationError, APIError

try:
    result = client.submit_bounty_claim(
        bounty_id="bounty_dos_port",
        claimant_miner_id="RTC_wallet_address",
        description="Valid description"
    )
except ValidationError as e:
    # Input validation failed
    print(f"Validation error: {e}")
except APIError as e:
    # API returned error response
    print(f"API error: {e.status_code} - {e}")
except BountyError as e:
    # Bounty-specific error
    print(f"Bounty error: {e.response}")
except Exception as e:
    # Connection or other errors
    print(f"Unexpected error: {e}")
```

## Claim Lifecycle

```
┌─────────────┐
│  Submitted  │
│  (pending)  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Under Review   │
│ (under_review)  │
└──────┬──────────┘
       │
       ├──────────────┐
       ▼              ▼
┌─────────────┐  ┌────────────┐
│   Approved  │  │  Rejected  │
│ (approved)  │  │ (rejected) │
└──────┬──────┘  └────────────┘
       │
       ▼
┌─────────────┐
│    Paid     │
│ (paid=1)    │
└─────────────┘
```

### Status Transitions

1. **pending**: Initial state when claim is submitted
2. **under_review**: Admin is reviewing the claim
3. **approved**: Claim approved, reward amount set
4. **rejected**: Claim rejected (with reviewer notes)
5. **paid**: Reward has been paid (payment_tx_id recorded)

## Database Schema

### bounty_claims Table

```sql
CREATE TABLE bounty_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT UNIQUE NOT NULL,
    bounty_id TEXT NOT NULL,
    claimant_miner_id TEXT NOT NULL,
    claimant_pubkey TEXT,
    submission_ts INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    github_pr_url TEXT,
    github_repo TEXT,
    commit_hash TEXT,
    description TEXT,
    evidence_urls TEXT,
    reviewer_notes TEXT,
    review_ts INTEGER,
    reviewer_id TEXT,
    reward_amount_rtc REAL,
    reward_paid INTEGER DEFAULT 0,
    payment_tx_id TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

### bounty_claim_evidence Table

```sql
CREATE TABLE bounty_claim_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    description TEXT,
    uploaded_at INTEGER NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES bounty_claims(claim_id)
);
```

## Testing

### Run Unit Tests

```bash
# Test bounty claims module
cd node/tests
pytest test_bounty_claims.py -v

# Test SDK integration
cd sdk/tests
pytest test_bounty_claims_sdk.py -v
```

### Test Coverage

The test suite covers:
- Payload validation (required fields, formats, lengths)
- Claim submission (success, duplicates, different bounties)
- Claim retrieval (by ID, by miner, by bounty)
- Status updates (all valid transitions, error cases)
- Payment tracking
- Statistics aggregation
- SDK method integration

## Security Considerations

1. **Admin Authentication**: All admin endpoints require `X-Admin-Key` header
2. **Duplicate Prevention**: Pending/under-review claims cannot be duplicated
3. **Input Validation**: Strict validation on all input fields
4. **Data Redaction**: Public endpoints redact sensitive miner information
5. **Rate Limiting**: Consider implementing rate limiting for claim submissions

## Integration with Existing Systems

### Node Integration

The bounty claims system integrates with the main RustChain node:

```python
# In rustchain_v2_integrated_v2.2.1_rip200.py
from bounty_claims import init_bounty_tables, register_bounty_endpoints

init_bounty_tables(DB_PATH)
register_bounty_endpoints(app, DB_PATH, os.environ.get("RC_ADMIN_KEY", ""))
```

### SDK Integration

The SDK provides high-level methods for all bounty operations:

```python
from rustchain import RustChainClient, BountyError

client = RustChainClient("https://rustchain.org")
bounties = client.list_bounties()
claims = client.get_miner_bounty_claims("RTC_miner_id")
```

## Troubleshooting

### Common Issues

**"Invalid bounty_id" Error**
- Ensure bounty_id matches one of the valid IDs exactly
- Check for typos or extra whitespace

**"Duplicate claim" Error**
- You can only have one pending/under-review claim per bounty
- Wait for existing claim to be approved/rejected before submitting again

**"Unauthorized" Error on Admin Endpoints**
- Include `X-Admin-Key` header with valid admin key
- Check that admin key matches `RC_ADMIN_KEY` environment variable

**Claim Not Found**
- Verify claim_id format (should start with "CLM-")
- Check that claim was successfully submitted

## Future Enhancements

- [ ] Email notifications for status changes
- [ ] Webhook integration for claim updates
- [ ] Multi-file evidence upload
- [ ] Claim comments/discussion thread
- [ ] Automated GitHub PR verification
- [ ] Bounty expiration dates
- [ ] Claim appeal process

## References

- [Bounties Configuration](../../bounties/dev_bounties.json)
- [RustChain SDK Documentation](../../sdk/README.md)
- [API Reference](../api/README.md)
- [Protocol Documentation](../PROTOCOL.md)
