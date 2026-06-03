# Self-Audit Report: warthog_verification.py

**File:** `node/warthog_verification.py`
**Lines:** 307
**Commit:** dca3c0b
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🔴 CRITICAL | No Actual Proof-of-Work Verification — Self-Reported Data Only | Lines 75-156 | 9.8 |
| 2 | 🔴 HIGH | Proof Freshness Uses Client-Supplied Timestamp | Lines 99-101 | 7.5 |
| 3 | 🟠 MEDIUM | Balance Validation with Float Comparison | Lines 126-130 | 6.5 |
| 4 | 🟠 MEDIUM | No Pool API Verification | Lines 140-153 | 6.3 |
| 5 | 🟡 LOW | No Rate Limiting on Proof Submissions | Lines 159-198 | 4.3 |

---

## Finding #1: No Actual Proof-of-Work Verification (CRITICAL)

**Location:** `verify_warthog_proof()` — Lines 75-156

**Description:**

The entire Warthog verification system relies exclusively on **self-reported, client-supplied data**. There is zero cryptographic verification of the underlying claim that the miner is actually mining Warthog.

For the **own_node** tier (1.15x bonus):
```python
# Lines 111-137
if proof_type == "own_node":
    node = proof.get("node")
    if not node.get("synced"):
        return False, WART_BONUS_NONE, "node_not_synced"
    height = node.get("height", 0)
    if not height or height < MIN_PLAUSIBLE_HEIGHT:
        return False, WART_BONUS_NONE, f"implausible_height_{height}"
    balance = float(proof.get("balance", "0"))
    if balance <= 0:
        return True, WART_BONUS_POOL, "node_no_balance_downgraded"
    return True, WART_BONUS_NODE, "own_node_verified"
```

The verification checks are:
1. `synced == True` — client reports it
2. `height >= 1000` — client reports it  
3. `balance > 0` — client reports it

**Every single one of these checks can be trivially bypassed by submitting fabricated data:**

```json
{
  "enabled": true,
  "proof_type": "own_node",
  "wart_address": "wart1qfake_address_1234567890",
  "node": {"height": 999999, "synced": true},
  "balance": "999999.99",
  "collected_at": 9999999999
}
```

This fabricated proof will pass all verification checks and grant the 1.15x bonus. The verifier never:
- Connects to the Warthog node's API to verify it exists
- Queries the Warthog blockchain to check the reported balance
- Validates the node height against actual Warthog chain state
- Verifies any cryptographic proof of mining work

For the **pool** tier (1.1x bonus):
```python
# Lines 140-153
if proof_type == "pool":
    pool = proof.get("pool")
    if pool.get("hashrate", 0) <= 0:
        return False, WART_BONUS_NONE, "pool_zero_hashrate"
    if not pool.get("url"):
        return False, WART_BONUS_NONE, "pool_url_missing"
    return True, WART_BONUS_POOL, "pool_mining_verified"
```

Same issue: the pool URL and hashrate are entirely self-reported. No pool API is contacted to verify the miner is actually contributing hashrate.

**Impact:** Any miner can claim the 1.1x or 1.15x Warthog bonus without actually mining Warthog. This undermines the integrity of the dual-mining incentive system and rewards dishonest miners at the expense of honest ones. If many miners exploit this, the bonus pool is effectively stolen from legitimate dual-miners.

**Remediation:**
- **Own node:** Connect to the miner's Warthog node API (e.g., `http://<miner_ip>:3000/api/status`) to verify: node is synced, height matches actual chain, address balance is verifiable on-chain
- **Pool mining:** Use the pool's public API (most pools expose `/api/accounts/<address>`) to verify the miner's WART address has submitted shares recently
- Implement a challenge-response protocol: the server issues a random nonce, and the miner must sign it with their Warthog wallet to prove ownership
- Add Merkle proof verification: miner provides a Merkle proof from a recent Warthog block showing their address received a reward

---

## Finding #2: Proof Freshness Uses Client-Supplied Timestamp (HIGH)

**Location:** Lines 99-101

**Description:**

```python
collected_at = proof.get("collected_at", 0)
if collected_at and abs(time.time() - collected_at) > MAX_PROOF_AGE:
    return False, WART_BONUS_NONE, "proof_too_old"
```

The `collected_at` timestamp is entirely controlled by the client. An attacker can simply set `collected_at` to the current time (`int(time.time())`) to bypass the staleness check, regardless of when the proof was actually collected.

This means the 15-minute freshness window (`MAX_PROOF_AGE = 900`) provides **no actual protection** against replay attacks. A proof collected months ago can be replayed as long as the attacker sets `collected_at` to a recent value.

**Impact:** The replay protection is entirely ineffective. Stale proofs can be replayed indefinitely by adjusting the client-supplied timestamp, allowing miners to claim Warthog bonuses without maintaining active mining operations.

**Remediation:**
- Use server-side timestamping: record when the proof is received, not when the client claims to have collected it
- Compare against the most recent proof submission time in the database, not against the client's claimed timestamp
- Add a nonce-based challenge-response: the server issues a time-limited nonce that must be included in the proof

---

## Finding #3: Balance Validation with Float Comparison (MEDIUM)

**Location:** Lines 126-130

**Description:**

```python
try:
    balance = float(balance_str)
except (ValueError, TypeError):
    balance = 0.0

if balance <= 0:
    return True, WART_BONUS_POOL, "node_no_balance_downgraded"
```

The balance is converted to a float for comparison. Using float for currency/balance comparisons can lead to precision issues:
- Very small balances (e.g., 0.0000000001) could be compared incorrectly
- Float precision loss for large balances (WART may have high precision)
- The `<= 0` check means a balance of exactly `0.0000000000001` passes, even if it's below the dust threshold

Additionally, the balance is stored as a TEXT in the database (line 55: `wart_balance TEXT`), meaning no numerical validation or constraint is enforced at the schema level.

**Impact:** While the immediate impact is low (most balances are clearly positive or zero), this could cause issues with edge cases, and the TEXT storage format provides no schema-level guarantee about balance validity.

**Remediation:**
- Use `Decimal` for balance comparisons
- Store balance as INTEGER (smallest unit) in the database
- Add a minimum balance threshold (e.g., `balance >= 1000` satoshis) to filter dust

---

## Finding #4: No Pool API Verification (MEDIUM)

**Location:** Lines 140-153

**Description:**

The pool mining verification accepts any pool URL and hashrate value without contacting the pool to verify the miner's claim. There is no:
- Whitelist of known/valid mining pools
- API call to verify the miner's address has active shares
- Validation of the pool URL format or existence
- Check that the hashrate is plausible for the miner's reported hardware

An attacker can submit:
```json
{"proof_type": "pool", "pool": {"url": "https://totally-fake-pool.example.com", "hashrate": 999999}}
```

And this will pass all checks, granting the 1.1x bonus.

**Impact:** Fake pool mining proofs grant unearned bonuses, inflating the attacker's rewards at the expense of legitimate miners.

**Remediation:**
- Maintain a whitelist of known pool APIs
- Contact the pool's API to verify the miner's address has submitted shares within the current epoch
- Validate the pool URL against known patterns (e.g., `https://*.acc-pool.pw/*`)

---

## Finding #5: No Rate Limiting on Proof Submissions (LOW)

**Location:** `record_warthog_proof()` — Lines 159-198

**Description:**

The `record_warthog_proof()` function uses `INSERT OR REPLACE` with `(miner, epoch)` as the PRIMARY KEY. While this prevents duplicate entries per epoch, there is no rate limiting on how many proof submissions a miner can make within an epoch.

A malicious miner could:
- Submit thousands of proofs per epoch with incrementally modified data (e.g., slightly different balances) to find the optimal bonus tier
- Flood the database with write operations, causing performance issues
- Attempt to race the settlement process by submitting a proof just before reward calculation

**Impact:** Minor denial-of-service potential and the ability to game the proof submission system.

**Remediation:**
- Enforce a minimum time between proof submissions (e.g., 1 proof per epoch per miner)
- Add a rate-limiting mechanism at the application layer
- Log and alert on excessive submission attempts

---

## Conclusion

The `warthog_verification.py` module has a **critical design flaw**: it verifies nothing. The entire bonus tier system is based on trusting client-supplied data without any external verification. This is the most severe finding across all audited files because it allows any miner to claim the Warthog bonus (up to 1.15x) without actually participating in Warthog mining.

**Priority fixes:**
1. **Implement server-side proof verification** — contact Warthog node APIs to verify claims (Finding #1, CRITICAL)
2. **Use server-side timestamps** — don't trust client `collected_at` values (Finding #2, HIGH)
3. **Add pool API verification** — verify mining activity with pool operators (Finding #4, MEDIUM)
