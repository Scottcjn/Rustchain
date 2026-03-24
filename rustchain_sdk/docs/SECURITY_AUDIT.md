# RustChain Security Audit Report

**Date:** 2026-03-14
**Scope:** `node/rustchain_v2_integrated_v2.2.1_rip200.py` (6343 lines), supporting modules
**Severity Scale:** CRITICAL / HIGH / MEDIUM / LOW / INFO

---

## Executive Summary

Audit of the RustChain v2.2.1 integrated node server covering SQL injection, authentication, input validation, rate limiting, SSRF, and insecure defaults. The codebase shows evidence of progressive hardening, but several exploitable issues remain.

---

## Findings

### 1. CRITICAL: Hardcoded Default Admin Key in Auth Checks

**Location:** Lines 3340, 3610, 4497, 4695, 4812
**Severity:** CRITICAL

Multiple endpoints compare the admin key against a hardcoded fallback default:
```python
if admin_key != os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64"):
```

If `RC_ADMIN_KEY` is not set in the environment, any attacker who knows this default string (which is committed to source control) can authenticate as admin to:
- `/withdraw/register` - register withdrawal keys (steal funds)
- `/withdraw/history/<miner_pk>` - enumerate withdrawal history
- `/api/miner/<miner_id>/attestations` - enumerate miner data
- `/ops/attest/debug` - dump internal config and MAC hashes
- `/ops/readiness` - inspect internal checks
- `/api/balances` - dump all wallet balances

Meanwhile, the startup guard at line 3650-3657 correctly refuses to start without `RC_ADMIN_KEY`. This means the hardcoded defaults in the above endpoints are dead code paths in normal operation, but they create a false sense of security if anyone deploys with `RC_ADMIN_KEY=""` (empty string) since the fallback kicks in.

**Fix:** Remove all hardcoded default values from `os.environ.get("RC_ADMIN_KEY", ...)` calls. Use the validated `ADMIN_KEY` module-level constant or the `is_admin()` / `admin_required` pattern consistently.

---

### 2. HIGH: SSRF via Unvalidated Node URL in `/api/nodes`

**Location:** Lines 4286-4293
**Severity:** HIGH

```python
import requests
for node in nodes:
    raw_url = node.get("url") or ""
    try:
        resp = requests.get(f"{raw_url}/health", timeout=3, verify=False)
```

The server makes an outbound HTTP request to every URL stored in `node_registry`, with `verify=False` (TLS bypass). An attacker who can register a node with a crafted URL (e.g., `http://169.254.169.254/latest/meta-data/`) can use this endpoint to:
- Probe internal network services (SSRF)
- Access cloud metadata endpoints (AWS/GCP/Azure credential theft)
- Scan internal ports

The `_should_redact_url` function only redacts the URL from the *response*, not from the *server-side request*. The `verify=False` also disables certificate validation.

**Fix:** Validate node URLs against an allowlist of schemes/hosts before making requests. Block RFC1918, link-local, loopback, and cloud metadata ranges. Remove `verify=False`.

---

### 3. HIGH: Inconsistent Admin Auth - Mixed Auth Patterns

**Location:** Throughout the file
**Severity:** HIGH

The codebase uses at least four different authentication patterns:
1. `admin_required` decorator (line 3659) - uses `ADMIN_KEY` constant
2. `is_admin()` function (line 2803) - checks `RC_ADMIN_KEY` env var
3. Inline comparison with hardcoded fallback (lines 3340, 3610)
4. `_wallet_review_ui_authorized()` (line 2829) - accepts query param auth

The query parameter auth pattern at line 2834 is particularly concerning:
```python
got = str(req.values.get("admin_key") or "").strip()
```
This accepts admin keys via URL query strings, which:
- Get logged in web server access logs
- May be cached in browser history
- Appear in Referer headers when navigating away

**Fix:** Standardize on `admin_required` decorator or `is_admin()`. Remove query parameter auth. Use only header-based auth for admin endpoints.

---

### 4. HIGH: Admin Key Leaked in HTML Templates

**Location:** Lines 3079, 3217, 3230, 3276
**Severity:** HIGH

The admin UI templates embed the admin key directly in HTML:
```html
<input type="hidden" name="admin_key" value="{{ admin_key }}">
<a href="/admin/wallet-review-holds/ui?admin_key={{ admin_key|urlencode }}">
```

This means:
- The admin key appears in page source, browser history, Referer headers
- It can be extracted by any XSS vulnerability
- Network proxies/CDNs may cache pages containing the key

**Fix:** Use session-based authentication or httponly cookies for admin UI instead of passing the key through templates and URL parameters.

---

### 5. MEDIUM: Potential SQL Injection via Dynamic Column/Table Names

**Location:** Line 5854
**Severity:** MEDIUM

```python
row = c.execute(f"SELECT {col} FROM balances WHERE {key} = ?", (wallet_id,)).fetchone()
```

While `col` and `key` are sourced from a hardcoded tuple (`("balance_rtc", "miner_pk")`, etc.) rather than user input, using f-string interpolation for column and table names is a dangerous pattern. If the source of these values ever changes to include user input, it becomes a direct SQL injection vector.

**Fix:** Validate column/key values against an explicit allowlist before interpolation, or restructure to avoid dynamic SQL column names.

---

### 6. MEDIUM: No Rate Limiting on Financial Endpoints

**Location:** Lines 3391, 3830, 5109, 5971
**Severity:** MEDIUM

The following sensitive endpoints have no rate limiting:
- `POST /withdraw/request` - withdrawal requests
- `POST /governance/propose` - create governance proposals
- `POST /governance/vote` - cast governance votes
- `POST /wallet/transfer` - admin transfers
- `POST /wallet/transfer/signed` - signed transfers

An attacker can:
- Spam withdrawal requests to drain balances
- Flood governance with proposals to dilute legitimate ones
- Enumerate valid wallet IDs via timing differences in balance checks

The attestation endpoint has IP-based rate limiting (15 unique miners/IP/hour), but financial endpoints lack equivalent protection.

**Fix:** Add per-IP and per-wallet rate limiting to all financial and governance endpoints.

---

### 7. MEDIUM: MAC Rate Limit Bypass - Enforcement Disabled

**Location:** Lines 1875-1876
**Severity:** MEDIUM

```python
# TEMP DISABLED FOR TESTING:             if unique_count > MAC_MAX_UNIQUE_PER_DAY:
# TEMP DISABLED FOR TESTING:                 return False, {"error": "mac_churn", ...}
```

The MAC address churn detection (designed to prevent Sybil attacks via rapid MAC cycling) is disabled. This was marked as temporary for testing, but remains in production code. An attacker can cycle through unlimited MAC addresses to create multiple identities from a single machine.

**Fix:** Re-enable MAC churn enforcement or replace with an alternative anti-Sybil mechanism.

---

### 8. MEDIUM: Museum Assets Endpoint - Path Traversal Risk

**Location:** Lines 2100-2105
**Severity:** MEDIUM

```python
@app.route("/museum/assets/<path:filename>", methods=["GET"])
def museum_assets(filename: str):
    return _send_from_directory(MUSEUM_DIR, filename)
```

Unlike the `/light-client/` endpoint (line 436), the museum assets endpoint does not check for `..` in the path. While Flask's `send_from_directory` has built-in path traversal protection, the inconsistency suggests a security review gap. Combined with potential Flask vulnerabilities or misconfigurations, this could allow directory traversal.

**Fix:** Add explicit path traversal checks consistent with the light-client endpoint pattern.

---

### 9. MEDIUM: VRF Seed Not Miner-Dependent

**Location:** Lines 2591-2592
**Severity:** MEDIUM

```python
seed = f"{CHAIN_ID}:{slot}:{epoch}".encode()
hash_val = hashlib.sha256(seed).digest()
```

The VRF selection seed is deterministic based only on chain ID, slot, and epoch. It does not include any per-miner randomness or unpredictable component. Any miner who knows these public values can predict who will be selected, enabling front-running or selective participation (only joining when selected).

**Fix:** Include miner-specific committed randomness in the VRF seed (e.g., hash of previous block + miner pubkey).

---

### 10. LOW: CORS Wildcard in beacon_x402.py

**Location:** `node/beacon_x402.py` line 95
**Severity:** LOW

```python
resp.headers["Access-Control-Allow-Origin"] = "*"
```

Wildcard CORS allows any origin to make requests to beacon endpoints. If these endpoints handle sensitive data or state changes, this could enable cross-origin attacks.

**Fix:** Restrict CORS to known frontend origins.

---

### 11. LOW: Error Messages Leak Internal Details

**Location:** Lines 3473, 4490, 5681
**Severity:** LOW

Several endpoints return raw exception messages:
```python
return jsonify({"error": f"Signature error: {e}"}), 400
return jsonify({'ok': False, 'error': str(e)}), 500
```

This can leak internal paths, database schema details, or library version information to attackers.

**Fix:** Return generic error messages to clients. Log detailed errors server-side only.

---

### 12. LOW: Bare `except` Clauses Silently Swallowing Errors

**Location:** Lines 2196, 2331, 2386, 2292, and many others
**Severity:** LOW

Multiple `except:` or `except Exception:` clauses silently catch and ignore errors:
```python
except:
    pass  # Race condition - another thread created it
```

This can mask security-relevant failures (e.g., failed integrity checks, database corruption) and make incident detection more difficult.

**Fix:** Log caught exceptions at WARNING level minimum. Use specific exception types.

---

### 13. INFO: Faucet IP Spoofing via X-Forwarded-For

**Location:** `faucet.py` lines 44-47
**Severity:** INFO

```python
if request.headers.get('X-Forwarded-For'):
    return request.headers.get('X-Forwarded-For').split(',')[0].strip()
```

The faucet trusts `X-Forwarded-For` unconditionally (no trusted proxy check). An attacker can bypass the 24-hour rate limit by setting arbitrary `X-Forwarded-For` headers.

The main node code (`client_ip_from_request`) correctly validates proxy trust before honoring forwarded headers.

**Fix:** Apply the same trusted proxy validation pattern from the main node.

---

### 14. INFO: Governance Proposal Sybil via Balance Threshold

**Location:** Lines 3846-3847
**Severity:** INFO

```python
if balance_rtc <= GOVERNANCE_MIN_PROPOSER_BALANCE_RTC:
```

The governance proposal threshold (10 RTC) only checks current balance. An attacker could:
1. Acquire 10+ RTC
2. Create proposal
3. Transfer balance away
4. Repeat with a different wallet

The vote weight is also checked at vote time but the proposal-creation gating is weak.

---

## Positive Findings

The codebase demonstrates several good security practices:

- **Parameterized SQL queries** throughout (no string-interpolated SQL for user data)
- **Replay protection** on withdrawals and signed transfers via nonce tracking
- **Two-phase commit** on transfers with 24-hour confirmation delay
- **Admin key minimum length** enforcement (32+ chars) at startup
- **Attestation input validation** with strict type checking and normalization
- **Hardware binding** to prevent multi-wallet attacks from single machines
- **Temporal consistency checks** to detect emulated fingerprints
- **Epoch replay protection** preventing double-reward distribution
- **Client IP normalization** with trusted proxy validation in main node

---

## Recommendations Summary

| Priority | Finding | Action |
|----------|---------|--------|
| P0 | Hardcoded admin key defaults | Remove all fallback defaults |
| P0 | SSRF in `/api/nodes` | Validate outbound URLs, block internal ranges |
| P1 | Admin key in templates/URLs | Switch to session-based admin auth |
| P1 | Mixed auth patterns | Standardize on `admin_required` decorator |
| P1 | No rate limiting on financial endpoints | Add per-IP/per-wallet rate limits |
| P2 | MAC enforcement disabled | Re-enable or replace |
| P2 | Museum path traversal check missing | Add `..` check |
| P2 | VRF seed predictable | Add miner-specific randomness |
| P3 | CORS wildcard | Restrict to known origins |
| P3 | Error message leaks | Genericize client-facing errors |
| P3 | Silent exception swallowing | Add logging |
| P4 | Faucet IP spoofing | Apply trusted proxy pattern |
