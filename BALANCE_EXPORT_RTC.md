# Balance Export API — RTC Wallet Confirmation

## RTC Wallet for Bounty #8361

Native Ed25519 RTC wallet created for claim compliance:

- Address: RTCce3ae9a6dd285211288bb6ebc0c41cbecf8538f1
- Created via: rtc-wallet create --name bounty-8361
- Wallet file: ~/.rustchain/wallets/bounty-8361.wallet (mode 600)
- Format verified: 43 chars, RTC prefix + 40 hex
- Balance check: https://rustchain.org/wallet/balance?miner_id=RTCce3ae9a6dd285211288bb6ebc0c41cbecf8538f1 → 0.0 RTC

This address replaces the EVM 0x... address previously used in PR #8361.

## Review Fixes Applied

All 8 items from review 5135460204 are addressed in this branch:

1. `/api/balances/export` now rate-limited (10/60s/IP), paginated (limit/offset ≤100), epoch-cached (30s), and tolerant of both `balances` schemas.
2. Pagination limits enforced: min 1, max 100, offset >=0.
3. Rate limit header `Retry-After` returned on 429.
4. Caching keys off current epoch to avoid heavy joins.
5. Schema tolerant: handles `amount_i64/miner_id` or `balance_rtc/miner_pk`.
6. Founder wallet classification preserved.
7. Public, read-only endpoint documented.
8. SPDX MIT license header added per BCOS checklist.

Branch pushed to fork: hummern:feature/balance-export-api
