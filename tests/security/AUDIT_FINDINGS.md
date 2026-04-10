# RustChain Security Audit (#2867)

## Summary
Conducted security review of UTXO transaction engine and related cryptographic modules. Found one medium-severity finding related to input validation on floating-point amount fields.

## Findings

### 1. Missing Upper-Bounds Validation on Transfer Amounts (Medium Severity)

**Location:** `node/utxo_endpoints.py`, lines 244-287, 331

**Issue:** The `/utxo/transfer` endpoint accepts `amount_rtc` and `fee_rtc` as floating-point numbers without validating maximum values. When converted to nanoRTC integers, this could allow unexpected behavior.

**Code:**
```python
# Line 244
amount_rtc = float(data.get('amount_rtc', 0))

# Line 260-261 (validation)
if amount_rtc <= 0:
    return jsonify({'error': 'Amount must be positive'}), 400

# Line 287 (conversion - no upper bound check)
amount_nrtc = int(amount_rtc * UNIT)  # UNIT = 100_000_000
```

**Risk:** 
- No constraint preventing amounts exceeding total RTC supply
- Allows sending requests with unrealistic values (1e20+ RTC)
- Could cause precision loss in float→int conversion
- Defensive layer present (coin selection rejects insufficient balance), but missing explicit bounds

**Recommendation:** 
Add explicit upper-bounds validation:
```python
MAX_RTC_SUPPLY = 8_388_608  # Total supply limit
if amount_rtc > MAX_RTC_SUPPLY:
    return jsonify({'error': 'Amount exceeds total RTC supply'}), 400
```

**PoC Test:** `tests/security/poc_integer_overflow.py`

## Additional Observations

### Strengths
- Double-spend prevention via `BEGIN IMMEDIATE` transactions (db layer)
- Input validation on transaction structure (non-negative outputs, conservation law)
- Ed25519 signature verification before UTXO state mutations
- Proper integer overflow protections in apply_transaction (lines 426-429)
- PRAGMA foreign_keys=ON in SQLite configuration

### Low-Risk Areas Reviewed
- P2P gossip protocol: HMAC authentication enforced, TLS verification configurable
- Hardware fingerprint: Uses secure hash computations
- No SQL injection found (all parameterized queries)
- No command injection found (no shell invocations with user input)

## Testing Methodology
- Source code review of transaction engine (node/*.py)
- Analysis of cryptographic boundaries
- Validation logic inspection
- Review of existing test cases

Wallet: neosmith1
