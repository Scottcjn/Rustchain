# x402 Payment Protocol — Red Team Security Audit Report

**Bounty:** Scottcjn/rustchain-bounties#66 (100 RTC)
**Auditor:** @Guzzzzzzzz
**Date:** 2026-05-20
**Scope:** `node/beacon_x402.py`, `node/rustchain_x402.py`, `node/x402_config.py`
**Commit:** `09cd06f9e28d4027bcb3992d1b43fe246fe6eadf`
**Wallet:** `Guzzzzzzzz`

---

## Executive Summary

This audit expands upon the existing red team report (by @B1tor) and header-presence-bypass finding (by @maelrx). While those reports identified the x402 payment bypass in `_check_x402_payment()`, **several additional vulnerabilities remain unpatched and unreported** across the x402 module surface.

This report identifies **5 new vulnerabilities** not covered by previous audits, plus confirms 2 of the 6 original findings remain unfixed on `main`.

| ID | Severity | Title | Component | Status |
|----|----------|-------|-----------|--------|
| GZ-01 | CRITICAL | Wallet Takeover via Unrestricted Coinbase Address Overwrite | `rustchain_x402.py` | **NEW** |
| GZ-02 | HIGH | Agent Wallet Hijack — No Ownership Verification | `beacon_x402.py` | **NEW** |
| GZ-03 | HIGH | Payment Verification Fail-Open when Config Loaded but Prices Zero | `beacon_x402.py` + `x402_config.py` | **NEW** |
| GZ-04 | MEDIUM | sys.path Injection via Hardcoded /root/shared Import | `rustchain_x402.py`, `beacon_x402.py` | **NEW** |
| GZ-05 | MEDIUM | Unclosed SQLite Connections in Error Paths | `rustchain_x402.py` | **NEW** |
| CONF-01 | CRITICAL | x402 Header Presence Bypass Still Unfixed on main | `beacon_x402.py` | CONFIRMED UNFIXED |
| CONF-02 | HIGH | No Payment Replay Protection | `beacon_x402.py` | CONFIRMED UNFIXED |

---

## GZ-01 — CRITICAL: Wallet Takeover via Unrestricted Coinbase Address Overwrite

**Component:** `node/rustchain_x402.py:97-147` — `/wallet/link-coinbase`
**CVSS:** 9.1 (Critical)
**CWE:** CWE-284 (Improper Access Control)

### Description

The `/wallet/link-coinbase` endpoint allows an admin to **overwrite any miner's coinbase_address without consent or notification**. There is no:

1. Confirmation from the miner whose wallet is being changed
2. Audit log of the previous address
3. Rate limiting on address changes
4. Notification mechanism to the affected miner

An attacker who obtains (or brute-forces, see RC-04/RC-05) the admin key can silently redirect **all future x402 payments** for any miner to their own Base address.

### Vulnerable Code

```python
@app.route("/wallet/link-coinbase", methods=["PATCH", "POST"])
def wallet_link_coinbase():
    # Admin key check only — no miner consent
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    # ...
    conn.execute(
        "UPDATE balances SET coinbase_address = ? WHERE miner_id = ?",
        (coinbase_address, actual_id),  # Overwrites without recording old address
    )
```

### Impact

- Silent fund redirection: admin (or compromised admin key) redirects all x402 payments
- No audit trail: the old coinbase_address is lost forever after overwrite
- Combined with RC-05 (hardcoded admin key default), this is **remotely exploitable on default deployments**

### Proof of Concept

```python
import requests

# Attacker uses default or leaked admin key
headers = {"X-Admin-Key": "rustchain_admin_key_2025_secure64"}
payload = {
    "miner_id": "victim_miner",
    "coinbase_address": "0xAttackerAddress0000000000000000000000"
}
resp = requests.post(
    "https://target-node/wallet/link-coinbase",
    json=payload, headers=headers, verify=False
)
# All future x402 payments for victim_miner now go to attacker
```

### Remediation

1. Log the old address before overwriting (audit table)
2. Require miner signature for address changes
3. Rate limit: max 1 address change per 24 hours per miner
4. Make address immutable after first set, or require multi-party confirmation

---

## GZ-02 — HIGH: Agent Wallet Hijack — No Ownership Verification

**Component:** `node/beacon_x402.py:182-220` — `/api/agents/<agent_id>/wallet`
**CVSS:** 7.5 (High)
**CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key)

### Description

The `set_agent_wallet` endpoint accepts **any `agent_id` in the URL path** and overwrites their wallet address. The admin key grants unrestricted access to modify any agent's wallet — there is no check that the admin is authorized to modify that specific agent.

The `ON CONFLICT ... DO UPDATE` clause means a second call with a different address **silently overwrites** the existing wallet. No immutability protection exists.

### Vulnerable Code

```python
@app.route("/api/agents/<agent_id>/wallet", methods=["POST", "OPTIONS"])
def set_agent_wallet(agent_id):
    # Only checks admin key, not agent ownership
    db.execute(
        "INSERT INTO beacon_wallets ... ON CONFLICT(agent_id) DO UPDATE SET coinbase_address = ...",
        (agent_id, address, time.time()),
    )
```

### Impact

- Admin can silently hijack any agent's payment destination
- No audit trail of address changes
- Combined with the default admin key (RC-05), any attacker can redirect agent payments

### Remediation

1. Make coinbase_address immutable after first set (remove ON CONFLICT DO UPDATE)
2. Require agent signature (via Ed25519 from relay_agents.pubkey_hex)
3. Add audit logging for all wallet changes

---

## GZ-03 — HIGH: Payment Verification Fail-Open when Config Loaded but Prices Zero

**Component:** `node/beacon_x402.py:119-161` + `node/x402_config.py:33-42`
**CVSS:** 7.2 (High)
**CWE:** CWE-287 (Improper Authentication)

### Description

The `is_free()` function treats ALL prices set to `"0"` as free. Since `x402_config.py` ships with ALL prices hardcoded to `"0"`, and `_check_x402_payment()` short-circuits when `is_free()` returns True, **all premium endpoints are free by default** even when `X402_CONFIG_OK = True`.

```python
# x402_config.py — ALL defaults are "0":
PRICE_BEACON_CONTRACT = "0"
PRICE_REPUTATION_EXPORT = "0"

# beacon_x402.py — short-circuits on free:
def _check_x402_payment(price_str, action_name):
    if not X402_CONFIG_OK or is_free(price_str):
        return True, None  # BYPASS
```

### Impact

- All "premium" endpoints are free on any deployment using default config
- The x402 payment infrastructure provides zero protection
- Operators may believe payments are active when they are not

### Remediation

1. Add startup warning when prices are "0" in non-dev environments
2. Require explicit `RC_X402_FREE_MODE=1` to enable free mode
3. Log every time `is_free()` bypasses a payment check

---

## GZ-04 — MEDIUM: sys.path Injection via Hardcoded /root/shared Import

**Component:** `node/rustchain_x402.py:25-27`, `node/beacon_x402.py:26-32`
**CVSS:** 5.3 (Medium)
**CWE:** CWE-426 (Untrusted Search Path)

### Description

Both x402 modules inject `/root/shared` into `sys.path` at import time:

```python
sys.path.insert(0, "/root/shared")
from x402_config import SWAP_INFO, WRTC_BASE, ...
```

If an attacker can write to `/root/shared/`, they can plant a malicious `x402_config.py` that redirects treasury addresses, disables payment gates, or executes arbitrary code at startup.

### Impact

- On multi-tenant/containerized deployments, `/root/shared` may be writable
- Treasury address silently redirected
- Arbitrary code execution at server startup

### Remediation

Use environment variable for config path instead of hardcoded path. Validate file integrity via hash before import.

---

## GZ-05 — MEDIUM: Unclosed SQLite Connections in Error Paths

**Component:** `node/rustchain_x402.py:121-140` — `wallet_link_coinbase()`
**CVSS:** 4.3 (Medium)
**CWE:** CWE-404 (Improper Resource Shutdown)

### Description

The `wallet_link_coinbase` endpoint creates a raw `sqlite3.connect()` connection but has multiple early-return and exception paths that skip `conn.close()`. Under sustained load, leaked connections cause SQLite locking errors and denial of service.

### Vulnerable Pattern

```python
conn = sqlite3.connect(db_path)
row = conn.execute(...).fetchone()
if not row:
    conn.close()  # Only closed on 404 path
    return jsonify({"error": ...}), 404

# If exception occurs here, conn is NEVER closed
conn.execute("UPDATE ...")
conn.commit()
conn.close()  # Only closed on success path
```

### Remediation

Use `with sqlite3.connect(db_path) as conn:` context manager.

---

## Confirmed Unfixed Vulnerabilities

### CONF-01: x402 Header Presence Bypass (Still on main)

The `_check_x402_payment()` in `beacon_x402.py` still only checks header presence. Original finding by @maelrx — confirmed unfixed on commit `09cd06f9`.

### CONF-02: No Payment Replay Protection

No `tx_hash` deduplication exists. The `x402_beacon_payments` table stores records but never checks for duplicates. Original finding by @B1tor (RC-03) — confirmed unfixed.

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| GZ-01: Wallet Takeover | CRITICAL | NEW |
| GZ-02: Agent Wallet Hijack | HIGH | NEW |
| GZ-03: Default Prices Bypass | HIGH | NEW |
| GZ-04: sys.path Injection | MEDIUM | NEW |
| GZ-05: Connection Leak DoS | MEDIUM | NEW |
| CONF-01: Header Bypass | HIGH | CONFIRMED |
| CONF-02: No Replay Protection | HIGH | CONFIRMED |

**Total new findings: 5** (1 Critical, 2 High, 2 Medium)

---

*Report prepared for RustChain Security Bounty Program — Issue #66*
*Wallet: `Guzzzzzzzz`*
