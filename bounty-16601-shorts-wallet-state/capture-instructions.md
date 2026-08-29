# Vertical Capture Instructions

Format: 1080×1920, 9:16, <=60 seconds.

## Shot plan

1. **0–5s — Hook card**
   - Full-screen text: `PENDING ≠ SETTLED`
   - Small footer: `RustChain wallet state in under a minute`

2. **5–15s — Endpoint card**
   - Show a clean terminal-style card with:
     `GET /wallet/history?miner_id=...&limit=10`
   - Do not show any private keys or real secret material.

3. **15–28s — State fields**
   - Animate three stacked labels:
     `pending`
     `confirmed`
     `failed`
   - Then reveal `confirmed_at` and `confirms_at` beside them.

4. **28–40s — Signed transfer state**
   - Show a simplified response card based on the public API reference:
     `phase: pending`
     `confirms_in_hours: 24`
   - Add small caption: `Documented API example — not a payment guarantee.`

5. **40–50s — Ledger flow**
   - Horizontal flow rendered vertically in four blocks:
     `Claim`
     ↓
     `Pending payment`
     ↓
     `Confirmed`
     ↓
     `Settled earnings`

6. **50–55s — Close**
   - Full-screen text: `Pending is promising. Confirmed is paid.`
   - End card: `github.com/Scottcjn/Rustchain`

## Rights / production notes
All visuals can be recreated from text and public API field names. No third-party footage, logos, music, or screenshots are required. If screenshots are used, capture only public documentation pages and crop out account/session details.
