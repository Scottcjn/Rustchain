# Sources and claim map

Primary source:
- RustChain Unified API Reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

Claim mapping:

1. `/wallet/history` is public and returns recent transfer history for a wallet.
   - Source: `docs/API_REFERENCE.md`, Wallet section, `GET /wallet/history`.

2. Wallet history exposes transfer status values `pending`, `confirmed`, and `failed`.
   - Source: `docs/API_REFERENCE.md`, `/wallet/history` field table.

3. Wallet history can include `confirmed_at` and `confirms_at` timestamps.
   - Source: `docs/API_REFERENCE.md`, `/wallet/history` example and field table.

4. Signed wallet transfers enter a pending phase before confirmation in the documented example.
   - Source: `docs/API_REFERENCE.md`, `POST /wallet/transfer/signed` response.

5. The API example documents `confirms_in_hours: 24` for a signed transfer.
   - Source: `docs/API_REFERENCE.md`, signed-transfer response and notes.

Editorial inference:
- Treating pending payments separately from settled earnings is an accounting/ledger recommendation made by this package, not a protocol guarantee or financial claim.

Canonical project:
- https://github.com/Scottcjn/Rustchain
