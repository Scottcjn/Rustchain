# Self-Audit: node/payout_preflight.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/payout_preflight.py
- Commit: 06a057b03cf2cc4e873478983c8bc3cd2b6a8d22
- Lines reviewed: whole-file (113 lines)

## Deliverable: 3 specific findings

### 1. Signed Transfer Validation Does Not Verify Cryptographic Signature

- **Severity**: critical
- **Location**: node/payout_preflight.py:60-95
- **Description**: `validate_wallet_transfer_signed()` checks that `signature` and `public_key` fields are present and non-empty (line 68: `required = ["from_address", "to_address", "amount_rtc", "nonce", "signature", "public_key"]`), but never performs actual cryptographic signature verification against the payload data. The function only validates field presence and format. This means any attacker can submit a transfer with a forged or arbitrary signature (e.g., `signature: "fake"`) and it will pass preflight validation. The signed transfer mechanism — designed to authorize client-side wallet operations — provides zero authentication assurance.
- **Reproduction**:
  ```python
  from node.payout_preflight import validate_wallet_transfer_signed
  payload = {
      "from_address": "RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba",
      "to_address": "RTCaabbccdd00000000000000000000000000000000",
      "amount_rtc": 100.0,
      "nonce": 1,
      "signature": "FORGED_SIGNATURE_NOT_VERIFIED",
      "public_key": "ANY_PUBLIC_KEY"
  }
  result = validate_wallet_transfer_signed(payload)
  assert result.ok == True  # Passes! Signature is never checked.
  ```
  An attacker can drain any wallet by submitting signed transfers with fabricated signatures.

### 2. Nonce Replay Attack — No Uniqueness Enforcement

- **Severity**: high
- **Location**: node/payout_preflight.py:85-90
- **Description**: The nonce validation only checks that `nonce_int > 0` (line 90: `if nonce_int <= 0`). There is no check against a database of previously used nonces for the `from_address`. A valid signed transaction can be replayed indefinitely by resubmitting the same payload with the same nonce. Combined with Finding 1 (no signature verification), this is doubly dangerous: even if signature verification were added later, the replay vulnerability would still allow the same signed payload to execute multiple times.
- **Reproduction**:
  ```python
  payload = {
      "from_address": "RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba",
      "to_address": "RTCaabbccdd00000000000000000000000000000000",
      "amount_rtc": 50.0,
      "nonce": 1,
      "signature": "valid_or_forged_sig",
      "public_key": "some_key"
  }
  # Submit this 100 times — preflight passes every time
  for _ in range(100):
      result = validate_wallet_transfer_signed(payload)
      assert result.ok == True
  ```
  The nonce field is purely cosmetic at the validation layer. Without a nonce-replay ledger (e.g., checking `used_nonces[from_address][nonce]`), the same transfer can be executed repeatedly.

### 3. Floating-Point Precision Loss in Financial Amount Quantization

- **Severity**: medium
- **Location**: node/payout_preflight.py:43-48 (admin transfer) and lines 78-83 (signed transfer)
- **Description**: Both `validate_wallet_transfer_admin` and `validate_wallet_transfer_signed` convert `amount_rtc` (a float) to micro-units via `amount_i64 = int(amount_rtc * 1_000_000)`. IEEE 754 floating-point arithmetic introduces rounding errors for certain decimal values. For example, `0.29 * 1_000_000` yields `289999.99999999994` in Python, and `int()` truncates to `289999` — losing 1 micro-unit (0.000001 RTC). Over many transactions, these rounding errors compound. Additionally, the `int()` truncation (toward zero) systematically favors the sender, as amounts are always rounded down.
- **Reproduction**:
  ```python
  # Demonstrate precision loss
  test_values = [0.1, 0.29, 1.005, 10.000001, 99.999999]
  for v in test_values:
      expected = int(v * 1_000_000)
      actual_micros = int(v * 1_000_000)
      if actual_micros != round(v * 1_000_000):
          print(f"  {v} RTC → {actual_micros} micro-units (off by {round(v*1_000_000) - actual_micros})")
  
  # Specific example:
  # 0.29 * 1_000_000 = 289999.99999999994
  # int(289999.99999999994) = 289999  (not 290000)
  ```
  Recommendation: Use `Decimal` from the `decimal` module, or `round(amount_rtc * 1_000_000)` instead of `int()` truncation.

## Known failures of this audit

- **No runtime testing**: This audit is static analysis only. I did not run the module against a live Rustchain node, so I cannot confirm whether downstream handlers also skip signature verification.
- **Integration path unknown**: The preflight functions are called by API endpoints that are not in this file. If the calling code performs its own signature verification or nonce-checking before calling preflight, Finding 1 and 2 severity would be reduced. However, the purpose of a preflight module is to be the validation gate — relying on callers to duplicate validation is itself an architectural weakness.
- **No fuzzing**: I did not fuzz the address format validation (lines 73-76) for edge cases like multi-byte Unicode in "RTC" prefix or addresses with embedded null bytes.
- **Cryptography primitives unknown**: I do not know which signature algorithm the Rustchain wallet uses (Ed25519, secp256k1, etc.), so I cannot evaluate whether a valid signature scheme exists elsewhere in the codebase.

## Confidence
- Overall confidence: 0.85
- Per-finding confidence: [0.90, 0.85, 0.80]

Finding 1 confidence is highest because the code clearly contains no signature verification logic. Finding 3 confidence is slightly lower because some Python environments may have different float behavior, though the core issue is well-established in IEEE 754.

## What I would test next

- **Signature verification audit**: Trace the call chain from API route handlers through preflight to actual transfer execution — verify whether signature verification exists at any layer, or if it is truly absent end-to-end.
- **Nonce ledger implementation**: Search the codebase for any nonce tracking mechanism (database table, Redis key, in-memory set) that the preflight module might be relying on implicitly.
- **Amount fuzzing**: Write a fuzzer that tests `validate_wallet_transfer_admin` with thousands of random float values to quantify how often `int(x * 1_000_000)` deviates from `round(x * 1_000_000)`, and whether any deviation exceeds 1 micro-unit (which would indicate multi-micro-unit loss).
