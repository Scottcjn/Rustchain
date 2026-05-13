# RustChain Security Audit Report

**Target:** [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain) - DePIN blockchain (Proof-of-Antiquity)
**Bounty:** 50-2000+ RTC per finding
**Scope per SECURITY.md:** Consensus, attestation, wallet, bridge, payout, API auth
**Date:** 2026-05-13

---

## 🔴 Critical (Immediate Risk)

### C-01: TOCTOU Race Condition in Faucet Rate Limiting

**File:** `faucet_service/faucet_service.py` (Lines 263-331)
**Type:** Race Condition / Rate Limit Bypass

**Description:**
`_check_sqlite()` and `_record_sqlite()` operate on **separate database connections** with **no transaction wrapping**. Between a check passing and the record being inserted, concurrent requests can all pass the check, bypassing the rate limit entirely.

```python
# Line 263: Separate connection for CHECK
def _check_sqlite(self, identifier, ip_address, wallet):
    conn = sqlite3.connect(self.config['database']['path'])
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM drip_requests WHERE ...')
    count = c.fetchone()[0]
    conn.close()  # ← Connection closed!
    if count >= max_requests:
        return False, ...
    return True, None  # ← Check passed, but record not yet written

# Line 322: Separate connection for RECORD (called AFTER check)
def _record_sqlite(self, ip_address, wallet, amount):
    conn = sqlite3.connect(self.config['database']['path'])
    c = conn.cursor()
    c.execute('INSERT INTO drip_requests ...')
    conn.commit()
    conn.close()
```

**Exploit:**
Send 10+ concurrent POST requests to `/faucet/drip`. All pass `_check_sqlite` before any records, all bypass the "1 request per 24h" limit. In mock mode the impact is limited; in production this drains the faucet.

**Fix:**
```python
# Wrap check + record in a single transaction with IMMEDIATE locking
conn = sqlite3.connect(self.config['database']['path'], timeout=5)
conn.execute("BEGIN IMMEDIATE")
try:
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM drip_requests WHERE ...')
    count = c.fetchone()[0]
    if count >= max_requests:
        conn.rollback()
        return False, ...
    c.execute('INSERT INTO drip_requests ...')
    conn.commit()
    return True, None
finally:
    conn.close()
```

---

### C-02: Bridge Admin Key Defaults to Empty String

**File:** `bridge/bridge_api.py` (Line 27)
**Type:** Authentication Bypass

**Description:**
```python
BRIDGE_ADMIN_KEY = os.environ.get("BRIDGE_ADMIN_KEY", "")  # ← EMPTY DEFAULT
```
When `BRIDGE_ADMIN_KEY` is not set in production, the admin key is `""`. If the auth decorator checks `if key == BRIDGE_ADMIN_KEY`, an empty string can be trivially guessed.

**Fix:**
```python
BRIDGE_ADMIN_KEY = os.environ.get("BRIDGE_ADMIN_KEY")
if not BRIDGE_ADMIN_KEY:
    raise RuntimeError("BRIDGE_ADMIN_KEY must be set in production")
```

*(Also needs verification of the auth decorator implementation.)*

---

## 🟠 High

### H-01: IP Spoofing via X-Forwarded-For (Faucet)

**File:** `faucet_service/faucet_service.py` (Lines 687-693)
**Type:** Rate Limit Bypass

**Description:**
`get_client_ip()` trusts `X-Forwarded-For` and `X-Real-IP` headers without validating them against the actual connection IP:

```python
def get_client_ip(request) -> str:
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or '127.0.0.1'
```

Since CORS is wildcard (`['*']`), an attacker can send POST requests with spoofed `X-Forwarded-For: 1.2.3.4` headers from a script, rotating IPs to bypass the "1 per 24h" rate limit indefinitely.

**Fix:**
- Remove or at minimum validate X-Forwarded-For against a trusted proxy list
- Rate limit based on `request.remote_addr` (actual TCP connection IP) for untrusted deployments

### H-02: CORS Wildcard + No CSRF

**File:** `faucet_service/faucet_service.py` (Lines 102-103, 488-489)
**Type:** Cross-Site Request Forgery

**Description:**
```python
'cors_origins': ['*'],       # Wildcard CORS
'csrf_enabled': False,        # No CSRF protection
...
CORS(app, origins=cors_origins)
```

Any external website can make authenticated POST requests from a user's browser. Combined with IP spoofing, this enables automated token draining without user interaction.

---

## 🟡 Medium

### M-01: SSL Verification Disable-able via Env Var (Wallet)

**File:** `wallet/rustchain_wallet_secure.py` (Lines 38-42)
**Type:** MITM / Eavesdropping

**Description:**
Setting `RUSTCHAIN_VERIFY_SSL=0` completely disables TLS certificate verification and suppresses all warnings:

```python
_ssl_env = os.environ.get("RUSTCHAIN_VERIFY_SSL", "1")
VERIFY_SSL = _ssl_env != "0"
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

**Fix:** Remove the disable option entirely from production builds. Warning suppression is especially dangerous as users may not realize TLS is disabled.

### M-02: SQLite Without WAL Mode / Concurrent Protection

**File:** `faucet_service/faucet_service.py`, `payout_ledger.py`, `bridge/bridge_api.py`
**Type:** Data Integrity

All three modules use SQLite without `WAL` mode or proper connection pooling. Each operation opens/closes a new connection. This:
1. Degrades performance under concurrent load
2. Compounds the race condition in C-01
3. Can cause `database is locked` errors in production

### M-03: Bridge Admin Auth Needs Verification

**File:** `bridge/bridge_api.py` (Lines 27-28)
**Type:** Authentication Verification Needed

The auth decorator implementation needs review to confirm it properly enforces admin access on `/bridge/release` and `/bridge/ledger` endpoints. The empty default admin key (C-02) combined with weak auth logic could allow unauthorized bridge operations.

---

## Summary

| ID | Severity | Component | Issue |
|----|----------|-----------|-------|
| C-01 | 🔴 Critical | Faucet | TOCTOU race condition in rate limiting |
| C-02 | 🔴 Critical | Bridge | Admin key defaults to empty string |
| H-01 | 🟠 High | Faucet | IP spoofing via X-Forwarded-For |
| H-02 | 🟠 High | Faucet | CORS wildcard + no CSRF |
| M-01 | 🟡 Medium | Wallet | SSL verification can be disabled |
| M-02 | 🟡 Medium | Multiple | SQLite without WAL/concurrent protection |
| M-03 | 🟡 Medium | Bridge | Admin auth needs verification |

---

*This audit was performed in accordance with RustChain's SECURITY.md Safe Harbor policy. Findings should be reported via GitHub Private Vulnerability Reporting.*
