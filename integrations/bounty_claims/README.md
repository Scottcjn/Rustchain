# RustChain Bounty Claims Integration

Complete integration package for the RustChain Bounty Claims System.

## Directory Structure

```
integrations/bounty_claims/
├── README.md                      # This file
├── example_bounty_integration.py  # Integration examples
└── ...
```

## Quick Start

### 1. Using the Python SDK

```python
from rustchain import RustChainClient, BountyError

client = RustChainClient("https://rustchain.org", verify_ssl=False)

# List bounties
bounties = client.list_bounties()

# Submit a claim
try:
    result = client.submit_bounty_claim(
        bounty_id="bounty_dos_port",
        claimant_miner_id="RTC_wallet_address",
        description="Completed MS-DOS validator",
        github_pr_url="https://github.com/user/rustchain-dos/pull/1"
    )
    print(f"Claim ID: {result['claim_id']}")
except BountyError as e:
    print(f"Error: {e}")

client.close()
```

### 2. Using Direct HTTP API

```bash
# List bounties
curl -sS https://rustchain.org/api/bounty/list | jq

# Submit a claim
curl -sS -X POST https://rustchain.org/api/bounty/claims \
  -H "Content-Type: application/json" \
  -d '{
    "bounty_id": "bounty_dos_port",
    "claimant_miner_id": "RTC_wallet_address",
    "description": "Completed MS-DOS validator",
    "github_pr_url": "https://github.com/user/rustchain-dos/pull/1"
  }' | jq

# Get claim details
curl -sS https://rustchain.org/api/bounty/claims/CLM-ABC123DEF456 | jq

# Get miner claims
curl -sS https://rustchain.org/api/bounty/claims/miner/RTC_wallet_address | jq

# Get statistics
curl -sS https://rustchain.org/api/bounty/statistics | jq
```

### 3. Run the Example Script

```bash
# Install dependencies
pip install requests

# Run example (shows code structure, doesn't make live calls)
python example_bounty_integration.py
```

## Available Bounties

| Bounty ID | Title | Reward |
|-----------|-------|--------|
| `bounty_dos_port` | MS-DOS Validator Port | Uber Dev Badge + RUST 500 |
| `bounty_macos_75` | Classic Mac OS 7.5.x Validator | Uber Dev Badge + RUST 750 |
| `bounty_win31_progman` | Win3.1 Progman Validator | Uber Dev Badge + RUST 600 |
| `bounty_beos_tracker` | BeOS / Haiku Native Validator | Uber Dev Badge + RUST 400 |
| `bounty_web_explorer` | RustChain Web Explorer | Uber Dev Badge + RUST 1000 |
| `bounty_relic_lore_scribe` | Relic Lore Scribe | Flamekeeper Lore Badge + RUST 350 |

## API Reference

See [BOUNTY_CLAIMS_SYSTEM.md](../../docs/BOUNTY_CLAIMS_SYSTEM.md) for complete API documentation.

## Claim Lifecycle

```
Submitted → Under Review → Approved → Paid
                ↓
            Rejected
```

### Status Values

- `pending`: Claim submitted, awaiting review
- `under_review`: Admin is reviewing the claim
- `approved`: Claim approved, reward amount set
- `rejected`: Claim rejected (with reviewer notes)
- `paid`: Reward has been paid

## Testing

### Unit Tests

```bash
# Test bounty claims module
cd node/tests
pytest test_bounty_claims.py -v

# Test SDK integration
cd sdk/tests
pytest test_bounty_claims_sdk.py -v
```

### Integration Testing

```bash
# Start local node
cd node
python rustchain_v2_integrated_v2.2.1_rip200.py

# In another terminal, run integration tests
python example_bounty_integration.py
```

## Admin Operations

Admin endpoints require the `X-Admin-Key` header:

```bash
# Update claim status
curl -sS -X PUT https://rustchain.org/api/bounty/claims/CLM-ABC123/status \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{
    "status": "approved",
    "reviewer_notes": "Excellent work!",
    "reward_amount_rtc": 500.0
  }' | jq

# Mark claim as paid
curl -sS -X POST https://rustchain.org/api/bounty/claims/CLM-ABC123/pay \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{
    "payment_tx_id": "tx_abc123def456"
  }' | jq
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid bounty_id` | bounty_id not in valid list | Use one of the 6 valid bounty IDs |
| `duplicate_claim` | Miner already has pending claim | Wait for existing claim to be processed |
| `Unauthorized` | Missing/invalid admin key | Include valid `X-Admin-Key` header |
| `Claim not found` | Invalid claim_id | Verify claim_id format (CLM-XXXXXXXXXXXX) |

### SDK Exception Handling

```python
from rustchain import BountyError
from rustchain.exceptions import ValidationError, APIError

try:
    result = client.submit_bounty_claim(...)
except ValidationError as e:
    # Input validation failed
    print(f"Invalid input: {e}")
except APIError as e:
    # API returned error
    print(f"API error: {e.status_code}")
except BountyError as e:
    # Bounty-specific error
    print(f"Bounty error: {e.response}")
```

## Database Schema

The bounty claims system uses SQLite tables:

- `bounty_claims`: Main claims table
- `bounty_claim_evidence`: Claim evidence/attachments
- `bounty_config`: Optional bounty configuration

See [BOUNTY_CLAIMS_SYSTEM.md](../../docs/BOUNTY_CLAIMS_SYSTEM.md#database-schema) for full schema.

## Integration Points

### Node Integration

The bounty claims module is automatically loaded by the main node:

```python
# In rustchain_v2_integrated_v2.2.1_rip200.py
from bounty_claims import init_bounty_tables, register_bounty_endpoints

init_bounty_tables(DB_PATH)
register_bounty_endpoints(app, DB_PATH, os.environ.get("RC_ADMIN_KEY", ""))
```

### SDK Integration

The SDK provides high-level methods:

- `list_bounties()`: List available bounties
- `submit_bounty_claim()`: Submit a new claim
- `get_bounty_claim()`: Get claim details
- `get_miner_bounty_claims()`: Get miner's claims
- `get_bounty_statistics()`: Get aggregate statistics

## Security Considerations

1. **Admin Authentication**: All admin endpoints require `X-Admin-Key`
2. **Duplicate Prevention**: Cannot submit duplicate pending claims
3. **Input Validation**: Strict validation on all fields
4. **Data Redaction**: Public endpoints hide sensitive data
5. **Rate Limiting**: Consider implementing for production

## Troubleshooting

### Claim submission fails

1. Check bounty_id is valid
2. Ensure miner_id is 1-128 characters
3. Verify description is 1-5000 characters
4. Check for duplicate pending claims

### Admin endpoints return 401

1. Include `X-Admin-Key` header
2. Verify admin key matches `RC_ADMIN_KEY` env var
3. Check for typos in admin key

### SDK import fails

```bash
# Install SDK in development mode
cd sdk
pip install -e .
```

## Related Documentation

- [Bounty Claims System](../../docs/BOUNTY_CLAIMS_SYSTEM.md) - Full documentation
- [SDK README](../../sdk/README.md) - SDK usage guide
- [API Reference](../../docs/api/README.md) - Complete API docs
- [Dev Bounties](../../bounties/dev_bounties.json) - Bounty configuration

## Contributing

To add new bounties:

1. Update `bounties/dev_bounties.json`
2. Add bounty ID to `VALID_BOUNTY_IDS` in `node/bounty_claims.py`
3. Update documentation

## License

MIT License - See [LICENSE](../../LICENSE) for details.
