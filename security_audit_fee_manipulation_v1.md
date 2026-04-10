# UTXO Endpoint Fee Manipulation Vulnerability

**Bounty**: #2819  
**Severity**: Medium  
**Date**: 2026-04-10  

## Summary

The `/utxo/transfer` endpoint does not include `fee_rtc` in Ed25519 signature verification. An attacker with network access can modify the fee after signing.

## Affected Code

- File: `node/utxo_endpoints.py`
- Lines: 273-283 (signature), 249, 288 (fee)

## Vulnerability

**Signed message** (lines 273-280) includes: amount, from, to, memo, nonce  
**Fee is NOT included**, so it can be modified after signing.

Attack:
1. Client signs: amount=10, fee=0.0001
2. Attacker changes: fee_rtc → 100 (in HTTP request)
3. Signature still validates (doesn't cover fee)
4. Transaction applies with inflated fee

## Fix

Include fee_rtc in signed message:

```python
tx_data = {
    'from': from_address,
    'to': to_address,
    'amount': amount_rtc,
    'fee': fee_rtc,  # ADD THIS
    'memo': memo,
    'nonce': nonce,
}
```

## Impact

- Financial loss (fee theft)
- Affects transaction integrity
- Requires MITM to exploit

All details in security_audit_fee_manipulation_v1.md
