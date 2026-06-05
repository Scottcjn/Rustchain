# RustChain Wallet History Verifier

Small T2 integration for bounty #13040. It verifies live wallet-history data
from a RustChain node without using secrets or signing transactions.

## Run

```bash
python integrations/FakerHideInBush-wallet-history/wallet_history_verifier.py \
  --miner-id RTCe0961d6b54f2fa96db57a373c84d8ad8986153f8
```

Optional flags:

- `--node https://50.28.86.131` selects the live node base URL.
- `--limit 10` limits history rows requested.
- `--strict-tls` requires normal TLS certificate verification. The default live
  IP endpoint is queried with certificate verification disabled because the IP
  endpoint is used directly by the RustChain wallet checks.

## Live Transcript

Run on 2026-06-04 UTC against `https://50.28.86.131`:

```text
RustChain wallet history verifier
node ok: version=2.2.1-rip200 db_rw=True
wallet: RTCe0961d6b54f2fa96db57a373c84d8ad8986153f8
transactions: 3 returned, total field=3
pending transfer_in total: 12.5 RTC
result: verified 3 transaction hash(es)
```

## What Is Verified

- `/health` reports a live node with `ok: true`.
- `/wallet/history` returns `ok: true` and echoes the requested wallet id.
- Each transaction has a numeric `amount`, a known `status`, and a 32-character
  hex `tx_hash`.
- Pending `transfer_in` amounts are summed for payout tracking.

This integration is read-only. It does not connect wallets, store secrets, sign
transactions, bridge, swap, or cash out funds.
