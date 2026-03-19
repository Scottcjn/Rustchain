# CLAUDE.md — RustChain Block Explorer Security Audit

## Context

Red team security audit of `explorer/enhanced-explorer.html` (PR #4).

**DO NOT use the original `enhanced-explorer.html` in production until all vulnerabilities are patched.**

## Vulnerabilities Found

| # | Severity | CVSS | Description |
|---|----------|------|-------------|
| 1 | 🔴 CRITICAL | 9.1 | Stored XSS via miner_id |
| 2 | 🔴 CRITICAL | 9.1 | Stored XSS via wallet address |
| 3 | 🔴 HIGH | 8.6 | Stored XSS via tx hash/from/to |
| 4 | 🟡 MEDIUM | 5.3 | No CORS validation on fetch |
| 5 | 🟢 LOW | 3.1 | No request debouncing |

## Files

| File | Purpose |
|------|---------|
| `explorer/SECURITY_REPORT.md` | Full security audit report |
| `explorer/patched/enhanced-explorer.html` | **HARDENED — use this** |
| `explorer/pocs/vuln1_miner_id_xss.html` | PoC for Vuln #1 |

## Quick Fix

Replace `enhanced-explorer.html` with `patched/enhanced-explorer.html`.

The patched version adds:
- `escapeHtml()` function for all innerHTML template literals
- Frame-busting protection
- All miner_id, architecture, wallet, tx.hash, tx.from, tx.to escaped
