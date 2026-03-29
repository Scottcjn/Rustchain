# Security Red Team Report: API Authentication & Rate Limiting

**Bounty:** #57 — API Auth Hardening (100 RTC)
**Auditor:** LaphoqueRC
**Date:** 2026-03-29
**Scope:** `rips/rustchain-core/api/rpc.py` (464 lines)
**Severity Scale:** Critical / High / Medium / Low / Info

---

## Executive Summary

The RustChain API server has **zero authentication and zero rate limiting**. All endpoints — including governance operations (create proposals, vote) and mining submission — are publicly accessible with wildcard CORS. This audit found **1 Critical, 2 High, 3 Medium, 1 Low** severity issues.

---

## Findings

### C1 — No Authentication on State-Changing Endpoints

**Severity:** Critical
**File:** `rips/rustchain-core/api/rpc.py`, lines ~290-330
**CVSS:** 9.8

**Description:**
All API endpoints are unauthenticated. The `_route_request()` method routes directly to handlers with no auth check:

```python
if path == "/api/mine":
    return self.api.rpc.call("submitProof", params)
if path == "/api/governance/create":
    return self.api.rpc.call("createProposal", params)
if path == "/api/governance/vote":
    return self.api.rpc.call("vote", params)
```

An anonymous user can:
- Submit fake mining proofs (`/api/mine`)
- Create governance proposals (`/api/governance/create`)
- Vote on proposals (`/api/governance/vote`)
- Query any wallet balance (`/api/wallet/<address>`)

**Impact:** Complete compromise of governance system. Attacker can create and pass proposals to change network parameters, mint tokens, or modify consensus rules.

**Remediation:**
1. Add API key authentication for state-changing endpoints
2. Require signed requests (wallet signature) for governance operations
3. Mining submissions should validate against registered miners

---

### H1 — No Rate Limiting

**Severity:** High
**File:** `rips/rustchain-core/api/rpc.py`, entire server

**Description:**
The API server has no rate limiting at any level. The `ApiRequestHandler` processes every request immediately. An attacker can:
- Send thousands of mining proofs per second
- Flood governance with proposals
- DDoS the node by exhausting its HTTP handler threads
- Scrape all wallet balances by iterating addresses

The `log_message()` method is also suppressed:
```python
def log_message(self, format, *args):
    """Suppress default logging"""
    pass
```

This means attack traffic leaves no logs.

**Impact:** DoS, data scraping, resource exhaustion, undetectable abuse.

**Remediation:**
1. Add per-IP rate limiting (e.g., 60 req/min for queries, 10 req/min for state changes)
2. Enable logging — at minimum log IP, endpoint, and timestamp
3. Consider connection limits per IP

---

### H2 — Wildcard CORS Allows Cross-Origin Attacks

**Severity:** High
**File:** `rips/rustchain-core/api/rpc.py`, line 337

**Description:**
```python
self.send_header("Access-Control-Allow-Origin", "*")
```

This allows any website to make API requests to a RustChain node on behalf of a visitor. A malicious webpage can:
- Query the visitor's wallet balance (if they're running a local node)
- Submit governance votes from the visitor's browser session
- Probe the node's internal state via JavaScript

**Impact:** Cross-origin data exfiltration, CSRF-like governance manipulation.

**Remediation:** Restrict CORS to known origins:
```python
allowed_origins = ["https://rustchain.org", "https://app.rustchain.org"]
origin = self.headers.get("Origin", "")
if origin in allowed_origins:
    self.send_header("Access-Control-Allow-Origin", origin)
```

---

### M1 — JSON-RPC Endpoint Exposes All Internal Methods

**Severity:** Medium
**File:** `rips/rustchain-core/api/rpc.py`, line ~325

**Description:**
The `/rpc` endpoint accepts arbitrary method names:
```python
if path == "/rpc":
    method = params.get("method", "")
    rpc_params = params.get("params", {})
    return self.api.rpc.call(method, rpc_params)
```

Any registered RPC method is callable. If internal/admin methods are registered (e.g., `shutdown`, `resetState`, `adjustDifficulty`), they're publicly accessible. There's no method whitelist for public access.

**Impact:** Exposure of internal administration functions.

**Remediation:** Maintain separate public and admin method registries. Only expose public methods via `/rpc`.

---

### M2 — Path Traversal in Dynamic Routes

**Severity:** Medium
**File:** `rips/rustchain-core/api/rpc.py`, lines ~300-315

**Description:**
Dynamic route parsing uses `path.split("/")[-1]`:
```python
if path.startswith("/api/wallet/"):
    address = path.split("/")[-1]
```

While not directly exploitable for file access, crafted paths like `/api/wallet/../admin/secret` may bypass route matching in unexpected ways. The address is passed unsanitized to handlers.

**Impact:** Potential route confusion, handler bypass.

**Remediation:** Validate address format (regex: `^RTC[a-f0-9]{40}$`) before passing to handlers.

---

### M3 — No Content-Length Validation

**Severity:** Medium
**File:** `rips/rustchain-core/api/rpc.py`, line ~270

**Description:**
```python
content_length = int(self.headers.get('Content-Length', 0))
body = self.rfile.read(content_length)
```

No maximum body size. An attacker can send a POST with `Content-Length: 999999999` and the server will attempt to read ~1GB into memory, causing OOM.

**Impact:** Denial of service via memory exhaustion.

**Remediation:** Cap `content_length` at a reasonable maximum (e.g., 1MB):
```python
MAX_BODY = 1024 * 1024  # 1MB
content_length = min(int(self.headers.get('Content-Length', 0)), MAX_BODY)
```

---

### L1 — Error Messages Leak Implementation Details

**Severity:** Low
**File:** `rips/rustchain-core/api/rpc.py`, `RpcRegistry.call()`

**Description:**
```python
except Exception as e:
    return ApiResponse(success=False, error=str(e))
```

Python exception strings often contain file paths, class names, and stack traces. These are returned directly to the client, revealing internal implementation details.

**Impact:** Information disclosure aiding further attacks.

**Remediation:** Return generic error messages to clients; log full exceptions server-side.

---

## Summary Table

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| C1 | Critical | No authentication on any endpoint | Open |
| H1 | High | No rate limiting + suppressed logs | Open |
| H2 | High | Wildcard CORS | Open |
| M1 | Medium | RPC exposes all internal methods | Open |
| M2 | Medium | No input validation on routes | Open |
| M3 | Medium | No body size limit (OOM DoS) | Open |
| L1 | Low | Exception details leaked to client | Open |
