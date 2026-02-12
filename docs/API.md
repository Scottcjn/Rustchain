# RustChain API Reference (Complete Public Endpoint Index)

Base URL: `https://50.28.86.131`

Notes:
- Use `-k` with curl because the node may use a self-signed TLS certificate.
- Endpoints marked `admin` require `X-Admin-Key` or `X-API-Key`.
- Endpoints marked `signed` require cryptographic signatures.

## Quick Health Checks

```bash
curl -sk https://50.28.86.131/health
curl -sk https://50.28.86.131/ready
curl -sk https://50.28.86.131/ops/readiness
```

## Read Endpoints (Public)

### Node and Chain State

```bash
# Node health
curl -sk https://50.28.86.131/health

# Ready check
curl -sk https://50.28.86.131/ready

# Readiness detail
curl -sk https://50.28.86.131/ops/readiness

# Prometheus metrics
curl -sk https://50.28.86.131/metrics

# mac-specific metrics
curl -sk https://50.28.86.131/metrics_mac

# Current epoch
curl -sk https://50.28.86.131/epoch

# Header tip
curl -sk https://50.28.86.131/headers/tip

# OUI enforce flag
curl -sk https://50.28.86.131/ops/oui/enforce

# Chain stats
curl -sk https://50.28.86.131/api/stats

# Known nodes
curl -sk https://50.28.86.131/api/nodes

# Miner list
curl -sk https://50.28.86.131/api/miners

# Explorer UI
curl -sk https://50.28.86.131/explorer

# OpenAPI spec
curl -sk https://50.28.86.131/openapi.json
```

### Rewards and Ledger

```bash
# Reward distribution by epoch
curl -sk https://50.28.86.131/rewards/epoch/62

# Wallet balance by miner_id
curl -sk "https://50.28.86.131/wallet/balance?miner_id=your_miner_id"

# Wallet ledger (global)
curl -sk https://50.28.86.131/wallet/ledger

# Wallet ledger (filtered)
curl -sk "https://50.28.86.131/wallet/ledger?miner_id=your_miner_id"

# All balances
curl -sk https://50.28.86.131/wallet/balances/all

# Pending transfers (default pending)
curl -sk https://50.28.86.131/pending/list

# Pending transfers (all statuses)
curl -sk "https://50.28.86.131/pending/list?status=all&limit=200"

# Integrity check
curl -sk https://50.28.86.131/pending/integrity
```

### Withdrawal Read APIs

```bash
# Withdrawal status
curl -sk https://50.28.86.131/withdraw/status/WD_1234567890_abcdef

# Withdrawal history
curl -sk "https://50.28.86.131/withdraw/history/your_miner_pk?limit=50"
```

### Download APIs

```bash
# Download landing page
curl -sk https://50.28.86.131/downloads

# Installer
curl -sk -OJ https://50.28.86.131/download/installer

# Miner package
curl -sk -OJ https://50.28.86.131/download/miner

# Uninstaller
curl -sk -OJ https://50.28.86.131/download/uninstaller

# Test miner files
curl -sk -OJ https://50.28.86.131/download/test
curl -sk -OJ https://50.28.86.131/download/test-bat
```

## Write Endpoints (Public, Signed, or Policy-Gated)

### Attestation and Enrollment

```bash
# Get attestation challenge nonce
curl -sk -X POST https://50.28.86.131/attest/challenge \
  -H "Content-Type: application/json" \
  -d '{}'

# Submit attestation
curl -sk -X POST https://50.28.86.131/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "nonce": "challenge_nonce",
    "device": {"family": "PowerPC", "arch": "G4"},
    "fingerprint": {},
    "signals": {}
  }'

# Enroll in epoch
curl -sk -X POST https://50.28.86.131/epoch/enroll \
  -H "Content-Type: application/json" \
  -d '{
    "miner_pubkey": "your_miner_pubkey",
    "miner_id": "your_miner_id",
    "device": {"family": "PowerPC", "arch": "G4"}
  }'

# Lottery eligibility
curl -sk "https://50.28.86.131/lottery/eligibility?miner_id=your_miner_id"
```

### Header and Mining Compatibility

```bash
# Submit signed block header
curl -sk -X POST https://50.28.86.131/headers/ingest_signed \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "header": {"slot": 12345},
    "message": "hex_message",
    "signature": "hex_signature"
  }'

# Legacy mine API (returns 410 Gone by design)
curl -sk -X POST https://50.28.86.131/api/mine -H "Content-Type: application/json" -d '{}'
curl -sk -X POST https://50.28.86.131/compat/v1/api/mine -H "Content-Type: application/json" -d '{}'
```

### Wallet and Withdrawals

```bash
# Signed wallet transfer (Ed25519)
curl -sk -X POST https://50.28.86.131/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTC...",
    "to_address": "RTC...",
    "amount_rtc": 1.25,
    "nonce": 1730000000,
    "signature": "hex_or_base64_sig",
    "public_key": "hex_pubkey",
    "memo": "test transfer"
  }'

# Register withdrawal key
curl -sk -X POST https://50.28.86.131/withdraw/register \
  -H "Content-Type: application/json" \
  -d '{
    "miner_pk": "your_miner_pk",
    "pubkey_sr25519": "hex_pubkey"
  }'

# Request withdrawal
curl -sk -X POST https://50.28.86.131/withdraw/request \
  -H "Content-Type: application/json" \
  -d '{
    "miner_pk": "your_miner_pk",
    "amount": 10.0,
    "destination": "destination_address",
    "signature": "base64_or_hex_signature",
    "nonce": "unique_nonce"
  }'
```

## Operator/Admin Endpoints (Protected)

These are not open user APIs. They are listed for completeness.

```bash
# Set miner header key (admin)
curl -sk -X POST https://50.28.86.131/miner/headerkey \
  -H "X-API-Key: $RC_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"miner_id":"your_miner_id","pubkey_hex":"64_hex_chars"}'

# Toggle OUI deny enforcement (admin)
curl -sk -X POST https://50.28.86.131/admin/oui_deny/enforce \
  -H "X-API-Key: $RC_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enforce": true}'

# OUI deny list (admin)
curl -sk -H "X-API-Key: $RC_ADMIN_KEY" https://50.28.86.131/admin/oui_deny/list
curl -sk -X POST -H "X-API-Key: $RC_ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"prefix":"AA:BB:CC"}' https://50.28.86.131/admin/oui_deny/add
curl -sk -X POST -H "X-API-Key: $RC_ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"prefix":"AA:BB:CC"}' https://50.28.86.131/admin/oui_deny/remove

# Rewards settle (admin/cron)
curl -sk -X POST https://50.28.86.131/rewards/settle \
  -H "Content-Type: application/json" \
  -d '{"epoch": 62}'

# Internal transfer (admin only)
curl -sk -X POST https://50.28.86.131/wallet/transfer \
  -H "X-Admin-Key: $RC_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from_miner":"A","to_miner":"B","amount_rtc":1.0,"reason":"admin_transfer"}'

# Pending worker/admin controls
curl -sk -X POST https://50.28.86.131/pending/void \
  -H "X-Admin-Key: $RC_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"pending_id":123,"reason":"manual void","voided_by":"admin"}'
curl -sk -X POST https://50.28.86.131/pending/confirm \
  -H "X-Admin-Key: $RC_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'

# Governance endpoints
curl -sk -X POST https://50.28.86.131/gov/rotate/stage   -H "X-API-Key: $RC_ADMIN_KEY" -H "Content-Type: application/json" -d '{}'
curl -sk        https://50.28.86.131/gov/rotate/message/62
curl -sk -X POST https://50.28.86.131/gov/rotate/approve -H "Content-Type: application/json" -d '{}'
curl -sk -X POST https://50.28.86.131/gov/rotate/commit  -H "X-API-Key: $RC_ADMIN_KEY" -H "Content-Type: application/json" -d '{}'

# Genesis export
curl -sk https://50.28.86.131/genesis/export
```

## Legacy Proxy (server_proxy.py)

If running the optional proxy service on port `8089`:

```bash
curl -s http://50.28.86.131:8089/status
curl -s http://50.28.86.131:8089/
curl -s http://50.28.86.131:8089/api/stats
```

## Related Docs

- `docs/PROTOCOL.md`
- `docs/GLOSSARY.md`
- `docs/tokenomics_v1.md`
- `docs/api/openapi.yaml`
