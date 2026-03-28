# Red Team Security Report — x402 Payment Protocol
## Bounty #66 | RustChain Security Audit

**Auditor:** @B1tor  
**Date:** 2026-03-28  
**Scope:** x402 payment middleware, MCP server, fleet immune system  
**RTC Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`

---

## Executive Summary

A red team audit of the RustChain x402 payment protocol integration identified **6 vulnerabilities** across critical payment verification paths. The most severe findings allow complete payment bypass without spending any RTC tokens. An attacker can access paid endpoints for free, replay past transactions, and potentially compromise admin functionality.

| ID | Severity | Title | Component |
|----|----------|-------|-----------|
| RC-01 | 🔴 CRITICAL | Testnet Mode Always-Accept | `mcp_server.py` |
| RC-02 | 🟠 HIGH | Payment Header Bypass | `middleware.py` |
| RC-03 | 🟠 HIGH | Payment Replay Attack | tx deduplication |
| RC-04 | 🟡 MEDIUM | Admin Key Timing Attack | `fleet_immune_system.py` |
| RC-05 | 🟡 MEDIUM | Hardcoded Admin Key Default | `fleet_immune_system.py` |
| RC-06 | 🔵 LOW | Wildcard CORS on Payment Endpoints | HTTP headers |

---

## RC-01 — CRITICAL: Testnet Mode Always-Accept

**Component:** `mcp_server.py`  
**CVSS Score:** 9.8 (Critical)

### Description

The `X402_TESTNET` environment variable defaults to `"1"` (testnet enabled). When testnet mode is active, any payment verification failure is silently swallowed and returns `valid: True`. This means **any request with any payment header — or even a crafted failure path — is accepted as a valid payment** in the default configuration.

### Vulnerable Code Pattern

```python
X402_TESTNET = os.environ.get("X402_TESTNET", "1")  # defaults to testnet ON

def verify_payment(payment_header):
    try:
        result = x402_lib.verify(payment_header)
        return result
    except Exception as e:
        if X402_TESTNET == "1":
            # Testnet: accept all failures as valid
            return {"valid": True, "testnet": True}
        raise
```

### Impact

- Complete bypass of payment verification in default deployments
- Attackers can access all paid API endpoints at zero cost
- Production deployments may unknowingly run with testnet mode enabled

### Remediation

1. Change default to `X402_TESTNET = os.environ.get("X402_TESTNET", "0")`
2. Never return `valid: True` on verification exception — fail closed
3. Add startup warning/error if testnet mode is detected in production context

---

## RC-02 — HIGH: Payment Header Bypass

**Component:** `middleware.py`  
**CVSS Score:** 8.6 (High)

### Description

When `X402_LIB_AVAILABLE=True`, the middleware checks for the presence of the `X-PAYMENT` header but **does not cryptographically verify its contents**. It logs the header value and proceeds to grant access. Any string value in the header — including `"fake"`, `"bypass"`, or `"1"` — is sufficient to pass the payment gate.

### Vulnerable Code Pattern

```python
if X402_LIB_AVAILABLE:
    payment_header = request.headers.get("X-PAYMENT")
    if payment_header:
        logger.info(f"Payment header present: {payment_header[:20]}...")
        # BUG: logs but never calls verify_payment()
        return grant_access(request)
    else:
        return payment_required_response()
```

### Impact

- Any HTTP client can bypass payment by adding `X-PAYMENT: x` to requests
- No RTC tokens are spent; blockchain is never queried
- Affects all endpoints protected by this middleware

### Remediation

1. Always call `verify_payment(payment_header)` and check `result["valid"] == True`
2. Never grant access based solely on header presence
3. Add integration test: `X-PAYMENT: invalid` must return 402, not 200

---

## RC-03 — HIGH: Payment Replay Attack

**Component:** Transaction deduplication layer  
**CVSS Score:** 8.1 (High)

### Description

The x402 payment processor does not maintain a spent-transaction cache or check against the blockchain for double-use. The same `tx_hash` from a single valid payment can be submitted **unlimited times** to access paid endpoints. There is no nonce, timestamp window, or deduplication store.

### Attack Scenario

```
1. Attacker makes one legitimate payment → receives tx_hash ABC123
2. Attacker sends 1000 requests with X-PAYMENT containing tx_hash ABC123
3. All 1000 requests succeed — attacker paid once, used service 1000x
```

### Impact

- Attackers pay once and gain unlimited access
- Revenue loss proportional to service usage
- Difficult to detect without blockchain cross-reference logging

### Remediation

1. Maintain an in-memory (or Redis) set of seen `tx_hash` values with TTL matching payment expiry
2. On each request, check: `if tx_hash in spent_transactions: return 402`
3. After verification, add: `spent_transactions.add(tx_hash)`
4. For distributed deployments, use a shared cache (Redis/Memcached)

---

## RC-04 — MEDIUM: Admin Key Timing Attack

**Component:** `fleet_immune_system.py`  
**CVSS Score:** 5.9 (Medium)

### Description

Admin key comparison uses Python's `!=` operator, which performs a **non-constant-time string comparison**. This enables timing side-channel attacks: an attacker can measure response times to deduce the admin key character-by-character.

### Vulnerable Code Pattern

```python
def authenticate_admin(provided_key):
    admin_key = os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64")
    if provided_key != admin_key:  # BUG: timing-vulnerable comparison
        raise AuthenticationError("Invalid admin key")
    return True
```

### Impact

- With ~100ms precision timing and ~1000 requests per character, the 40-char key could be recovered in ~40,000 requests
- Accelerated if attacker is co-located or on low-latency connection
- Enables admin takeover without brute force of full key space

### Remediation

```python
import hmac
if not hmac.compare_digest(provided_key.encode(), admin_key.encode()):
    raise AuthenticationError("Invalid admin key")
```

---

## RC-05 — MEDIUM: Hardcoded Admin Key Default

**Component:** `fleet_immune_system.py`  
**CVSS Score:** 5.5 (Medium)

### Description

The admin key falls back to a hardcoded default value if `RC_ADMIN_KEY` is not set in the environment. This default value is **publicly visible in the source code** and any deployment that omits the environment variable uses a known-compromised key.

### Vulnerable Code

```python
admin_key = os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64")
```

### Impact

- Any node deployed without explicit `RC_ADMIN_KEY` env var is immediately compromised
- Default key is trivially discoverable from the public repository
- Enables fleet-wide admin access for anyone who reads the source

### Remediation

1. **Remove the default entirely** — raise an error if `RC_ADMIN_KEY` is not set:
   ```python
   admin_key = os.environ.get("RC_ADMIN_KEY")
   if not admin_key:
       raise EnvironmentError("RC_ADMIN_KEY must be set — no default allowed")
   ```
2. Add to deployment documentation and docker-compose examples
3. Add a startup check that rejects operation without the key

---

## RC-06 — LOW: Wildcard CORS on Payment Endpoints

**Component:** HTTP response headers  
**CVSS Score:** 3.5 (Low)

### Description

Payment endpoints return `Access-Control-Allow-Origin: *`, allowing any web origin to make authenticated cross-origin requests. While payment tokens themselves are still required, this broadens the attack surface for CSRF-style payment relay attacks and leaks response metadata to third-party sites.

### Vulnerable Header

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: X-PAYMENT, Authorization, Content-Type
```

### Impact

- Malicious web pages can silently relay payment headers from a victim's browser
- Response bodies (including error messages with tx details) leak cross-origin
- Combined with RC-02, allows cross-site payment bypass escalation

### Remediation

1. Restrict CORS to known origins:
   ```python
   ALLOWED_ORIGINS = ["https://app.rustchain.io", "https://wallet.rustchain.io"]
   ```
2. Never use `*` when `Authorization` or custom headers like `X-PAYMENT` are involved
3. Use `Access-Control-Allow-Credentials: false` explicitly

---

## Proof of Concept

See `security/x402-poc/test_x402_vulns.py` for executable PoC scripts demonstrating RC-01 through RC-06.

---

## Recommended Fix Priority

| Priority | Finding | Estimated Effort |
|----------|---------|-----------------|
| Immediate | RC-01: Testnet default | 5 min — change default string |
| Immediate | RC-02: Header bypass | 1 hour — add verify call |
| High | RC-03: Replay attack | 4 hours — add tx cache |
| Medium | RC-04: Timing attack | 15 min — use hmac.compare_digest |
| Medium | RC-05: Hardcoded key | 30 min — remove default |
| Low | RC-06: CORS | 1 hour — configure allowlist |

---

*Report prepared for RustChain Security Bounty Program — Issue #66*
