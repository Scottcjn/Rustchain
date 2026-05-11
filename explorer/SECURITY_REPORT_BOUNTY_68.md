# Bounty 68 Security Report: Explorer API Response Injection

## Summary

The current explorer renders several API-provided identifiers through `innerHTML` after shortening them, but before HTML escaping the display text. A malicious miner ID, transaction hash, wallet address, block hash, or dashboard field returned by the API could be interpreted as markup in the browser.

The patch escapes shortened values at the sink in:

- `explorer/static/js/explorer.js`
- `explorer/static/js/dashboard.js`
- `explorer/dashboard/app.py`
- `explorer/dashboard/agent-economy.html`
- `explorer/dashboard/agent-economy-v2.html`
- `explorer/dashboard/miners.html`
- `explorer/enhanced-explorer.html`
- `explorer/miner-dashboard.html`
- `explorer/realtime-explorer.html`
- `explorer/templates/dashboard.html`
- `explorer/templates/ws_explorer.html`

## Finding 1: Main Explorer API Response Injection

Severity: High

Affected file: `explorer/static/js/explorer.js`

Affected sinks included miner IDs, block hashes, transaction hashes, and transaction wallet addresses. These values were placed into template literals assigned to `innerHTML`; `title` attributes were escaped, but the visible cell text was not.

Example vulnerable pattern:

```js
`${shortenAddress(miner.miner_id || 'unknown')}`
```

Impact: If a miner-controlled identifier or chain/API response contains HTML with an event handler, the explorer can execute attacker-controlled JavaScript when the table renders.

Fix: Wrap shortened values with `escapeHtml(...)` before inserting them into `innerHTML`.

## Finding 2: Real-Time Dashboard API Response Injection

Severity: High

Affected file: `explorer/static/js/dashboard.js`

The real-time dashboard repeated the same pattern for top miners, recent blocks, recent transactions, and the hardware legend. Values from API/WebSocket state were rendered into HTML without escaping.

Fix: Add a local `escapeHtml` utility and apply it to every API-derived text value that remains in `innerHTML` templates.

## Finding 3: Compact Flask Dashboard Proxy Injection

Severity: High

Affected file: `explorer/dashboard/app.py`

The compact Flask dashboard proxies `/api/dashboard` data and renders miner and transaction fields directly into table rows with `innerHTML`.

Impact: A malicious upstream API response can execute script in a user browser viewing the local dashboard.

Fix: Add an `esc(...)` JavaScript helper and escape all proxied table cells, including timestamps after formatting.

## Finding 4: Legacy Dashboard Template Injection

Severity: High

Affected files:

- `explorer/dashboard/miners.html`
- `explorer/dashboard/agent-economy.html`
- `explorer/dashboard/agent-economy-v2.html`
- `explorer/enhanced-explorer.html`
- `explorer/miner-dashboard.html`
- `explorer/realtime-explorer.html`
- `explorer/templates/dashboard.html`
- `explorer/templates/ws_explorer.html`

These dashboard views used `innerHTML` to render miner, block, transaction, reward, attestation, notification, and architecture fields directly from fetched or WebSocket-delivered data. The patch adds local escaping helpers, sanitizes CSS class fragments, URL-encodes block links, and replaces one URL share-link `innerHTML` assignment with DOM node construction.

## PoC

Open `explorer/pocs/bounty68_api_response_xss.html` locally. The unsafe table demonstrates the pre-patch sink class; the patched table renders the same payload as text.

## Verification

Run:

```sh
python3 -m pytest explorer/test_security_hardening.py
```
