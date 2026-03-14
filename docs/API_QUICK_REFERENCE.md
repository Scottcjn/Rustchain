# RustChain API Quick Reference

A concise reference for the most commonly used RustChain API endpoints.

## Node Health

```bash
# Check node health
curl -sk https://rustchain.org/health

# Get current epoch
curl -sk https://rustchain.org/epoch
```

## Wallet

```bash
# Check wallet balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# Send signed transfer
curl -sk -X POST https://rustchain.org/wallet/transfer/signed \
  -H 'Content-Type: application/json' \
  -d '{
    "from_address": "RTCabc123...",
    "to_address": "RTCdef456...",
    "amount_rtc": 10.0,
    "memo": "Payment",
    "nonce": 1733420000000,
    "signature": "<ed25519_hex>",
    "public_key": "<pubkey_hex>"
  }'
```

## Mining

```bash
# List active miners
curl -sk https://rustchain.org/api/miners

# Submit attestation
curl -sk -X POST https://rustchain.org/attest/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "miner": "YOUR_WALLET",
    "device": { "arch": "x86_64", "cores": 4 },
    "fingerprint": { "checks": {} },
    "signals": {},
    "report": {}
  }'
```

## Block Explorer

```bash
# View explorer (browser)
open https://rustchain.org/explorer

# Get block by height
curl -sk "https://rustchain.org/api/block?height=100"
```

## Governance

```bash
# List proposals
curl -sk https://rustchain.org/governance/proposals

# View proposal detail
curl -sk https://rustchain.org/governance/proposal/1

# Create proposal (requires >10 RTC)
curl -sk -X POST https://rustchain.org/governance/propose \
  -H 'Content-Type: application/json' \
  -d '{
    "wallet": "RTC...",
    "title": "Proposal Title",
    "description": "Rationale and details"
  }'

# Submit signed vote
curl -sk -X POST https://rustchain.org/governance/vote \
  -H 'Content-Type: application/json' \
  -d '{
    "proposal_id": 1,
    "wallet": "RTC...",
    "vote": "yes",
    "nonce": "1700000000",
    "public_key": "<ed25519_pubkey_hex>",
    "signature": "<ed25519_signature_hex>"
  }'
```

## Rewards

```bash
# Check reward eligibility
curl -sk "https://rustchain.org/api/rewards/eligibility?miner_id=YOUR_WALLET"

# Get all balances
curl -sk https://rustchain.org/api/rewards/balances

# Get round-robin status
curl -sk https://rustchain.org/api/rewards/round-robin
```

## Bridge (wRTC)

```bash
# Swap info (USDC/wRTC)
curl -sk https://rustchain.org/wallet/swap-info
```

| Resource | Link |
|----------|------|
| Swap wRTC on Raydium | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| Price Chart | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| Bridge RTC ↔ wRTC | [BoTTube Bridge](https://bottube.ai/bridge) |
| Base Bridge | [BoTTube Base Bridge](https://bottube.ai/bridge/base) |

## x402 Premium Endpoints

Currently free while proving the flow:

```bash
# Bulk video export (BoTTube)
curl -sk https://bottube.ai/api/premium/videos

# Deep agent analytics (BoTTube)
curl -sk https://bottube.ai/api/premium/analytics/

# Full reputation export (Beacon Atlas)
curl -sk https://rustchain.org/api/premium/reputation
```

## Error Codes

| Code | Meaning |
|------|---------|
| `MISSING_MINER` | No `miner` or `miner_id` field in request |
| `INVALID_MINER` | Miner ID contains invalid characters |
| `INVALID_DEVICE` | Device metadata is malformed |
| `INVALID_FINGERPRINT` | Fingerprint data is malformed |
| `INVALID_SIGNALS` | Signal metadata is malformed |

## Rate Limits

- Attestation: 1 per epoch per miner
- Balance queries: No limit
- Transfer: Requires valid signature

## Notes

- All endpoints use HTTPS. Use `-sk` flags with curl because nodes may use self-signed certificates.
- 1 RTC = 1,000,000 uRTC (micro-RTC) internally.
- Epoch duration: 10 minutes (600 seconds), 144 slots per epoch.
- Ed25519 signatures are required for transfers and governance votes.

---

*See [full API documentation](API.md) for detailed endpoint specifications.*
