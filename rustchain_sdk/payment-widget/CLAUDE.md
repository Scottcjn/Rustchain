# CLAUDE.md — RustChain Payment Widget Security Audit

## Context

This is a **Red Team security audit** of the RustChain Payment Widget (`payment-widget/rustchain-pay.js`), merged in PR #13.

**DO NOT deploy the original `rustchain-pay.js` in production until all 5 vulnerabilities are patched.**

## Files

| File | Purpose |
|------|---------|
| `payment-widget/rustchain-pay.js` | **VULNERABLE — DO NOT USE** Original widget code |
| `pocs/vuln1_xss_via_data_attributes.html` | PoC: Stored XSS via data-memo/data-to |
| `pocs/vuln2_xss_via_label.html` | PoC: Stored XSS via data-label |
| `pocs/vuln3_clickjacking.html` | PoC: Clickjacking via iframe overlay |
| `pocs/vuln4_csrf_callback.html` | PoC: CSRF via callback URL |
| `patched/rustchain-pay.js` | **HARDENED — Use this version** |
| `SECURITY_REPORT.md` | Full security audit report |
| `CLAUDE.md` | This file |

## Vulnerabilities Found

1. 🔴 **CRITICAL** — Stored XSS via `data-memo` / `data-to` (CVSS 9.3)
2. 🔴 **HIGH** — Stored XSS via `data-label` (CVSS 8.1)
3. 🟡 **MEDIUM** — Clickjacking via iframe (CVSS 6.1)
4. 🟡 **MEDIUM** — CSRF via callback URL (CVSS 6.5)
5. 🟢 **LOW** — Missing amount validation

## Quick Fix (to apply to production)

Replace `rustchain-pay.js` with `patched/rustchain-pay.js`. The patched version adds:
- `escapeHtml()` function
- Frame-busting (`blockFraming()`)
- Origin validation on callbacks
- Amount bounds checking
- All template literal injections sanitized

## Testing

All PoC files can be opened directly in a browser (no server required) to demonstrate each vulnerability.
