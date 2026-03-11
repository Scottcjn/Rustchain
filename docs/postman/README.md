# RustChain API Postman Collection

**Issue #1617** - Complete Postman collection for RustChain Node API

## Overview

This directory contains a complete Postman collection and environment configuration for testing and documenting the RustChain Node API. The collection is organized by functionality with example responses for each endpoint.

## Files

| File | Description |
|------|-------------|
| `RustChain_API.postman_collection.json` | Complete Postman collection with all endpoints |
| `RustChain_Environment.postman_environment.json` | Environment variables configuration |
| `validate_postman_collection.py` | Validation script and checklist |
| `README.md` | This documentation file |

## Quick Start

### 1. Import Collection into Postman

1. Open Postman (v10.0 or later recommended)
2. Click **File** → **Import**
3. Select `RustChain_API.postman_collection.json`
4. Collection will appear in the sidebar

### 2. Import Environment

1. Click **File** → **Import**
2. Select `RustChain_Environment.postman_environment.json`
3. Click the environment dropdown (top right)
4. Select **RustChain API Environment**

### 3. Configure Variables

Update the following environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `base_url` | RustChain node URL | `https://rustchain.org` |
| `miner_id` | Your miner ID/wallet | `eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC` |
| `admin_key` | Admin API key (secret) | `your-admin-key` |
| `wallet_address` | Your wallet address | `your-walletRTC` |
| `recipient_address` | Recipient wallet for transfers | `recipient-walletRTC` |

## Collection Structure

The collection is organized into logical folders:

```
RustChain API - Complete Collection
├── 01_Health_Status
│   ├── Health Check
│   └── Readiness Probe
├── 02_Epoch_Network
│   ├── Current Epoch
│   ├── Network Statistics
│   ├── Active Miners
│   └── Hall of Fame
├── 03_Fee_Pool
│   └── Fee Pool Statistics
├── 04_Wallet_Balance
│   ├── Miner Balance
│   └── Lottery Eligibility
├── 05_Explorer
│   └── Block Explorer
├── 06_Attestation
│   └── Submit Attestation
├── 07_Wallet_Transfers
│   ├── Admin Transfer
│   └── Signed Transfer
└── 08_Withdrawals
    └── Withdrawal Request
```

## Endpoints Reference

### Public Endpoints (No Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Node health check |
| GET | `/ready` | Readiness probe |
| GET | `/epoch` | Current epoch, slot, enrolled miners |
| GET | `/api/stats` | Network statistics |
| GET | `/api/miners` | Active miners with attestation data |
| GET | `/api/hall_of_fame` | Hall of Fame leaderboard |
| GET | `/api/fee_pool` | RIP-301 fee pool statistics |
| GET | `/balance?miner_id=X` | Miner balance lookup |
| GET | `/lottery/eligibility?miner_id=X` | Epoch eligibility check |
| GET | `/explorer` | Block explorer HTML page |

### Authenticated Endpoints (X-Admin-Key Header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/attest/submit` | Submit hardware attestation |
| POST | `/wallet/transfer` | Admin transfer |
| POST | `/wallet/transfer/signed` | Ed25519 signed transfer |
| POST | `/withdraw/request` | Withdrawal request |

## Example Usage

### Test Health Endpoint

```bash
curl -sk https://rustchain.org/health | jq .
```

Expected response:
```json
{
  "ok": true,
  "uptime_s": 58480,
  "version": "2.2.1-rip200",
  "backup_age_hours": 13.65,
  "db_rw": true,
  "tip_age_slots": 0
}
```

### Test Epoch Endpoint

```bash
curl -sk https://rustchain.org/epoch | jq .
```

Expected response:
```json
{
  "epoch": 91,
  "slot": 13227,
  "enrolled_miners": 20,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "total_supply_rtc": 8388608
}
```

### Test Miner Balance

```bash
curl -sk "https://rustchain.org/balance?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC" | jq .
```

Expected response:
```json
{
  "balance": 150.5,
  "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC"
}
```

### Submit Attestation (Authenticated)

```bash
curl -sk -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{
    "miner_id": "your_miner_id",
    "proof": {
      "clock_skew": {"mean_ppm": 15.2, "std_ppm": 3.1},
      "cache_timing": {"l1_latency_ns": 4.2, "l2_latency_ns": 12.5},
      "simd_identity": {"has_avx2": false, "has_altivec": true},
      "thermal_entropy": {"jitter_score": 0.85},
      "instruction_jitter": {"fpu_jitter": 0.023, "int_jitter": 0.018},
      "behavioral_heuristics": {"vm_detected": false, "hypervisor": null, "cpu_vendor": "Freescale"}
    },
    "signature": "base64_signature"
  }' | jq .
```

## Validation Script

Run the validation script to verify the collection structure:

```bash
# Make executable
chmod +x validate_postman_collection.py

# Run validation
python3 validate_postman_collection.py

# Run with live API tests (optional)
python3 validate_postman_collection.py --live-test
```

The script will:
- Validate JSON syntax
- Check collection structure
- Verify environment variables
- Generate endpoint checklist
- Optionally test live endpoints

## Validation Checklist

Use this checklist to verify all endpoints:

### Health & Status
- [ ] GET `/health` - Returns node health status
- [ ] GET `/ready` - Returns readiness status

### Epoch & Network
- [ ] GET `/epoch` - Returns current epoch info
- [ ] GET `/api/stats` - Returns network statistics
- [ ] GET `/api/miners` - Returns active miners list
- [ ] GET `/api/hall_of_fame` - Returns leaderboard

### Fee Pool
- [ ] GET `/api/fee_pool` - Returns fee pool statistics

### Wallet
- [ ] GET `/balance?miner_id=X` - Returns miner balance
- [ ] GET `/lottery/eligibility?miner_id=X` - Returns eligibility status

### Explorer
- [ ] GET `/explorer` - Returns HTML explorer page

### Attestation (Admin)
- [ ] POST `/attest/submit` - Submits hardware attestation

### Transfers (Admin)
- [ ] POST `/wallet/transfer` - Executes admin transfer
- [ ] POST `/wallet/transfer/signed` - Executes signed transfer

### Withdrawals (Admin)
- [ ] POST `/withdraw/request` - Creates withdrawal request

## Environment Variables Reference

### Required Variables

| Variable | Type | Description |
|----------|------|-------------|
| `base_url` | default | RustChain node base URL |
| `miner_id` | default | Your miner identifier |
| `admin_key` | secret | Admin API key for authenticated endpoints |

### Optional Variables

| Variable | Type | Description |
|----------|------|-------------|
| `wallet_address` | default | Your wallet address |
| `recipient_address` | default | Recipient for transfers |
| `tx_payload` | default | Base64-encoded transaction payload |
| `signature` | secret | Ed25519 signature |
| `attestation_proof` | default | Hardware attestation proof JSON |
| `environment` | default | Environment name (production/staging) |
| `api_version` | default | API version string |

## Testing Tips

### 1. Start with Public Endpoints

Test public endpoints first to verify connectivity:
- Health Check
- Readiness Probe
- Epoch Info

### 2. Use Pre-request Scripts

For authenticated endpoints, add a pre-request script to generate timestamps:

```javascript
// Generate timestamp for nonce
pm.environment.set("timestamp", Math.floor(Date.now() / 1000));
```

### 3. Use Collection Variables

Store responses in variables for use in subsequent requests:

```javascript
// Save miner_id from response
const jsonData = pm.response.json();
pm.environment.set("miner_id", jsonData.miner_id);
```

### 4. Add Tests

Add test scripts to validate responses:

```javascript
// Test status code
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

// Test response body
pm.test("Node is healthy", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData.ok).to.be.true;
});
```

## Error Handling

### Common Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 400 | Bad Request | Check request body format |
| 401 | Unauthorized | Verify X-Admin-Key header |
| 404 | Not Found | Check miner_id or endpoint URL |
| 429 | Rate Limited | Wait and retry |
| 500 | Server Error | Contact node operator |

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error description",
  "detail": "Additional error details (optional)"
}
```

## API Rate Limits

| Endpoint Type | Limit |
|---------------|-------|
| Public endpoints | 100 requests/minute |
| Attestation | 1 per 10 minutes per miner |
| Transfers | 10 per minute per wallet |

## Security Notes

- **Never commit** admin keys or signatures to version control
- Use Postman's **secret** type for sensitive variables
- Consider using Postman **vault** for team sharing
- Rotate admin keys periodically

## Troubleshooting

### Collection Import Fails

1. Ensure Postman v10.0 or later
2. Verify JSON syntax: `python3 -m json.tool RustChain_API.postman_collection.json`
3. Re-download the collection file

### Environment Variables Not Working

1. Ensure environment is selected (top-right dropdown)
2. Check variable names match exactly (case-sensitive)
3. Verify variable values don't have extra whitespace

### Authenticated Endpoints Return 401

1. Verify admin key is correct
2. Check X-Admin-Key header is being sent
3. Ensure environment is active

### SSL Certificate Warnings

The RustChain node uses self-signed certificates. In Postman:
1. Go to Settings → General
2. Disable "SSL certificate verification"
3. Or use `curl -sk` for CLI testing

## Contributing

To add new endpoints:

1. Add request to appropriate folder (or create new folder)
2. Include example responses (success and error cases)
3. Update this README with endpoint details
4. Run validation script to verify structure

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-11 | Initial complete collection (Issue #1617) |

## Resources

- [OpenAPI Specification](../api/openapi.yaml)
- [API Documentation](../API.md)
- [RustChain Documentation](../README.md)

## License

This Postman collection is part of the RustChain project documentation.

---

**Issue**: rustchain-bounties #1617  
**Status**: Complete  
**Validated**: Yes
