# x402 Payment Protocol — Red Team Security Audit Report (v2)

**Bounty:** Scottcjn/rustchain-bounties#66 (100 RTC)
**Auditor:** @Guzzzzzzzz
**Date:** 2026-05-20
**Scope:** `node/beacon_x402.py`, `node/rustchain_x402.py`, `node/x402_config.py`
**Commit:** `09cd06f9e28d4027bcb3992d1b43fe246fe6eadf`
**Wallet:** `Guzzzzzzzz`

---

## Executive Summary

This audit expands upon the existing red team report (by @B1tor) and header-presence-bypass finding (by @maelrx). This report identifies **5 new findings** across the x402 module surface.

| ID | Severity | Title | Component |
|----|----------|-------|-----------|
| GZ-01 | HIGH | Wallet Address Overwrite Without Audit Trail | `rustchain_x402.py` |
| GZ-02 | HIGH | Agent Wallet Overwrite — No Immutability or Ownership Check | `beacon_x402.py` |
| GZ-03 | MEDIUM | Default Free-Mode Pricing Lacks Operator Warning | `x402_config.py` |
| GZ-04 | MEDIUM | sys.path Injection via Hardcoded /root/shared Import | both x402 modules |
| GZ-05 | LOW | SQLite Connection Not Managed via Context Manager | `rustchain_x402.py` |

> **Note on threat model:** GZ-01 and GZ-02 assume a compromised admin key. These modules correctly return 503 when `RC_ADMIN_KEY` / `BEACON_ADMIN_KEY` is unset (no default fallback). The risk is post-compromise privilege escalation, not unauthenticated access.

---

## GZ-01 — HIGH: Wallet Address Overwrite Without Audit Trail

**Component:** `node/rustchain_x402.py:97-147` — `/wallet/link-coinbase`
**CVSS:** 7.1 (High)
**CWE:** CWE-778 (Insufficient Logging), CWE-284 (Improper Access Control)

### Description

The `/wallet/link-coinbase` endpoint allows an admin to **overwrite any miner's coinbase_address** with no:

1. Audit log recording the previous address value
2. Rate limiting on address changes per miner
3. Notification mechanism to the affected miner
4. Confirmation step or cooldown period

If an admin key is compromised (e.g., via leaked environment variables, log exposure, or the RC-05 timing attack from @B1tor's report), the attacker can silently redirect payment destinations.

### Vulnerable Code

```python
conn.execute(
    "UPDATE balances SET coinbase_address = ? WHERE miner_id = ?",
    (coinbase_address, actual_id),
)
# BUG: old coinbase_address is lost — no audit record
```

### Impact

- **Post-compromise escalation:** A compromised admin key enables silent fund redirection
- **No forensics:** Without an audit table, operators cannot detect or revert unauthorized changes
- **No rate limiting:** Attacker can rapidly cycle through all miners

### Proof of Concept

```python
# With a valid admin key, overwrite any miner's wallet:
resp1 = client.post('/wallet/link-coinbase',
    json={"miner_id": "victim", "coinbase_address": "0x" + "11" * 20},
    headers={"X-Admin-Key": ADMIN_KEY})
# resp1.status_code == 200, legitimate address set

resp2 = client.post('/wallet/link-coinbase',
    json={"miner_id": "victim", "coinbase_address": "0x" + "AA" * 20},
    headers={"X-Admin-Key": ADMIN_KEY})
# resp2.status_code == 200, silently overwritten — no trace of old address
```

### Remediation

1. Create `coinbase_address_audit` table recording old/new addresses with timestamp
2. Log all address changes at WARNING level
3. Add a rate limit (max 1 change per 24h per miner)
4. Consider requiring miner signature for address changes

---

## GZ-02 — HIGH: Agent Wallet Overwrite — No Immutability or Ownership Check

**Component:** `node/beacon_x402.py:182-220` — `/api/agents/<agent_id>/wallet`
**CVSS:** 6.8 (High)
**CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key)

### Description

The `set_agent_wallet` endpoint uses `ON CONFLICT(agent_id) DO UPDATE` which allows **unlimited silent overwrites** of any agent's wallet address. A single compromised admin key can redirect payments for all agents.

### Vulnerable Code

```python
db.execute(
    """INSERT INTO beacon_wallets (agent_id, coinbase_address, created_at)
       VALUES (?, ?, ?)
       ON CONFLICT(agent_id) DO UPDATE SET coinbase_address = excluded.coinbase_address""",
    (agent_id, address, time.time()),
)
```

### Impact

- No immutability: wallet address can be changed unlimited times
- No ownership verification: admin can modify any agent's wallet
- No audit trail of changes

### Remediation

1. Make `coinbase_address` immutable after initial set (use `INSERT OR IGNORE` instead of `ON CONFLICT DO UPDATE`)
2. For updates, require a separate admin-approved migration endpoint with audit logging
3. Add agent signature verification for wallet changes

---

## GZ-03 — MEDIUM: Default Free-Mode Pricing Lacks Operator Warning

**Component:** `node/x402_config.py:33-42`
**CVSS:** 4.3 (Medium)
**CWE:** CWE-1188 (Insecure Default Initialization of Resource)

### Description

All prices in `x402_config.py` default to `"0"` (free). While this is **documented** as intentional beta/development pricing, and `/api/x402/status` reports `pricing_mode: free`, there is no startup log warning to alert operators that payment gates are inactive.

An operator who deploys with `X402_CONFIG_OK=True` (config imported successfully) might assume payments are enforced, but `is_free("0")` bypasses all payment checks silently.

> **Clarification from v1:** This is an operational hardening recommendation, not a payment bypass vulnerability. The free pricing is intentional and documented.

### Current Behavior

```python
# x402_config.py — documented as free beta pricing:
PRICE_BEACON_CONTRACT = "0"     # Future: "10000"  = $0.01

# _check_x402_payment short-circuits:
if not X402_CONFIG_OK or is_free(price_str):
    return True, None  # silently bypasses — no log entry
```

### Remediation

1. Add startup log at WARNING level: `"x402 prices are $0 (free mode) — payment gates inactive"`
2. Log each `is_free()` bypass at DEBUG level for observability
3. Consider requiring `RC_X402_FREE_MODE=1` env var to explicitly opt into free mode

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

On multi-tenant or containerized deployments where `/root/shared` is writable by other processes, an attacker can plant a malicious `x402_config.py` that:

1. Overrides `BEACON_TREASURY` to redirect payments
2. Makes `is_free()` always return `True`
3. Executes arbitrary code at server startup

### Impact

- Module imported at startup — malicious code executes with server privileges
- Treasury address can be silently redirected
- Requires write access to `/root/shared/` (secondary prerequisite)

### Remediation

Use environment variable for config path:
```python
config_path = os.environ.get("RC_X402_CONFIG_PATH", "")
```

---

## GZ-05 — LOW: SQLite Connection Not Managed via Context Manager

**Component:** `node/rustchain_x402.py:121-140` — `wallet_link_coinbase()`
**CVSS:** 3.1 (Low)
**CWE:** CWE-404 (Improper Resource Shutdown)

### Description

The `wallet_link_coinbase` endpoint creates a raw `sqlite3.connect()` connection without using a context manager. While the 404 path explicitly calls `conn.close()`, an unexpected exception between `connect()` and `close()` would leak the connection.

> **Clarification from v1:** The explicit `conn.close()` calls on both the 404 and success paths handle normal flows correctly. This is a defensive coding recommendation, not a demonstrated leak.

### Current Code

```python
conn = sqlite3.connect(db_path)
# ... multiple operations ...
conn.close()  # present on both 404 and success paths
```

### Remediation

Use `with sqlite3.connect(db_path) as conn:` for automatic cleanup on any exception.

---

## Summary

| Finding | Severity | Category |
|---------|----------|----------|
| GZ-01: Wallet Overwrite No Audit | HIGH | Post-compromise escalation |
| GZ-02: Agent Wallet No Immutability | HIGH | Post-compromise escalation |
| GZ-03: Free-Mode No Warning | MEDIUM | Operational hardening |
| GZ-04: sys.path Injection | MEDIUM | Supply chain risk |
| GZ-05: Connection Management | LOW | Defensive coding |

**Threat model note:** GZ-01 and GZ-02 require a compromised admin key. These modules do NOT have hardcoded default keys — they return 503 when the key is not configured.

---

*Report prepared for RustChain Security Bounty Program — Issue #66*
*Wallet: `Guzzzzzzzz`*
