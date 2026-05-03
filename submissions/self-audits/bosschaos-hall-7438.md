# Self-Audit Report: hall_of_rust.py

**File:** `node/hall_of_rust.py`
**Lines:** 766
**Commit:** 57e9e41
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🟠 MEDIUM | No Authentication on `/hall/induct` — Arbitrary Machine Induction | Line 147-237 | 6.5 |
| 2 | 🟠 MEDIUM | Exception Detail Disclosure in HTTP Responses | Lines 236, 333 | 5.3 |
| 3 | 🟠 MEDIUM | Truncated SHA-256 Fingerprint — Collision Risk | Line 156 | 6.0 |
| 4 | 🟡 LOW | Rust Score Manipulation via Self-Reported Hardware Data | Lines 83-121 | 4.3 |
| 5 | 🟡 LOW | No Rate Limiting on Hall Endpoints | Multiple | 4.3 |

---

## Finding #1: No Authentication on /hall/induct (MEDIUM)

**Location:** `induct_machine()` — Lines 147-237

**Description:**

```python
@hall_bp.route('/hall/induct', methods=['POST'])
def induct_machine():
    data = request.json or {}
    # No authentication check!
    hw_serial = data.get('cpu_serial', data.get('hardware_id', 'unknown'))
    fp_data = f"{data.get('device_model', '')}{data.get('device_arch', '')}{hw_serial}"
    fingerprint_hash = hashlib.sha256(fp_data.encode()).hexdigest()[:32]
```

The `/hall/induct` endpoint accepts POST requests without any authentication or authorization checks. Any caller can:
- Induct arbitrary machines with any hardware profile
- Spoof device model, architecture, CPU serial
- Set arbitrary `miner_id` values
- Create unlimited Hall of Rust entries

Unlike other RustChain endpoints (e.g., `anti_double_mining.py` which verifies signatures), this endpoint trusts all input data without any proof of ownership or hardware verification.

**Impact:** An attacker could flood the Hall of Rust with fake entries, spoof legacy hardware profiles to game the Rust Score leaderboard, or create entries for machines that don't exist. The leaderboard (used for display/gamification) becomes unreliable.

**Remediation:**
- Require a signed attestation from a verified node before induction
- Cross-reference the hardware fingerprint with existing attestation records
- Add authentication: require an API key or bearer token

---

## Finding #2: Exception Detail Disclosure (MEDIUM)

**Location:** Lines 236, 333

**Description:**

```python
except Exception as e:
    return jsonify({'error': str(e)}), 500
```

Both `induct_machine()` (line 236) and `set_eulogy()` (line 333) return raw exception messages to the caller. These messages may contain:
- Database file paths (`/root/rustchain/rustchain_v2.db`)
- SQL error messages with table/column names
- Stack traces
- Internal file system structure

An attacker can intentionally trigger errors (e.g., sending malformed JSON, invalid field types) to gather reconnaissance about the system architecture, database schema, and file locations.

**Impact:** Information disclosure aids in further attacks. Knowledge of database paths and schema helps target SQL injection or data exfiltration attempts.

**Remediation:**
- Return generic error messages in production: `{'error': 'Internal server error'}`
- Log detailed errors server-side only
- Use a custom error handler that sanitizes exception messages

---

## Finding #3: Truncated SHA-256 Fingerprint — Collision Risk (MEDIUM)

**Location:** Line 156

**Description:**

```python
fingerprint_hash = hashlib.sha256(fp_data.encode()).hexdigest()[:32]
```

The SHA-256 hash is truncated to 32 hex characters (16 bytes = 128 bits). While 128 bits is still large, the birthday paradox means collision probability becomes non-trivial with approximately 2^64 entries. More importantly, the input to the hash (`fp_data = f"{device_model}{device_arch}{cpu_serial}"`) is entirely user-controlled and easily manipulated.

An attacker can craft two different hardware profiles that produce the same fingerprint:
- `device_model="PentiumIII"`, `device_arch="x86"`, `cpu_serial="ABC123"`
- Any other combination where the concatenated string produces the same hash

Since the input space is limited (hardware models and serials are finite and predictable), a targeted collision attack is feasible.

**Impact:** An attacker could create a collision with a legitimate machine's fingerprint, allowing them to "steal" that machine's Hall of Rust entry, modify its attestation count, or mark it as deceased.

**Remediation:**
- Use the full SHA-256 hash (64 hex characters)
- Include additional entropy in the fingerprint: node ID, attestation signature, timestamp
- Use HMAC with a server-side secret key instead of plain SHA-256

---

## Finding #4: Rust Score Manipulation via Self-Reported Data (LOW)

**Location:** `calculate_rust_score()` — Lines 83-121

**Description:**

The Rust Score is calculated from self-reported hardware attributes:
- `manufacture_year` — derived from `device_model` and `device_arch` (user-controlled)
- `total_attestations` — incremented on each induction call
- `thermal_events` — self-reported counter
- `device_arch` — user-controlled, with arch bonuses up to 150 points (486)

An attacker can maximize their score by:
1. Claiming to be a 486 processor (+150 arch bonus)
2. Setting `device_model` to a capacitor plague era model (+bonus)
3. Fabricating a 1980s manufacture year (age bonus: 45 years × weight)
4. Calling `/hall/induct` repeatedly to boost attestation count

**Impact:** The Rust Score leaderboard becomes unreliable. While this is primarily a gamification feature, a corrupted leaderboard undermines the Hall of Rust's purpose.

**Remediation:**
- Cross-reference claimed hardware with attestation records
- Cap the attestation bonus to prevent grinding
- Validate manufacture year against known hardware release dates

---

## Finding #5: No Rate Limiting on Hall Endpoints (LOW)

**Location:** All `/hall/*` endpoints

**Description:**

None of the Hall of Rust endpoints implement rate limiting. The `/hall/induct` endpoint (POST) is particularly vulnerable to abuse:
- Unlimited POST requests allowed
- Each request opens and closes a database connection
- No IP-based throttling

An attacker could flood the endpoint to cause database I/O pressure or fill the database with spam entries.

**Impact:** Denial of service through resource exhaustion. Database growth from spam entries.

**Remediation:**
- Add rate limiting: max 1 induction per IP per minute
- Implement request counting and block excessive callers
- Use connection pooling instead of open/close per request

---

## Conclusion

The `hall_of_rust.py` module is a gamification feature that tracks hardware machines in the RustChain network and scores them by "rustiness." The most significant finding is the lack of authentication on the induction endpoint (Finding #1), which allows arbitrary data injection into the Hall of Rust database. The truncated fingerprint hash (Finding #3) introduces collision risk that could allow fingerprint spoofing.

Priority fixes:
1. **Add authentication** to `/hall/induct` (Finding #1)
2. **Sanitize error messages** — prevent detail disclosure (Finding #2)
3. **Use full SHA-256** — prevent fingerprint collisions (Finding #3)
