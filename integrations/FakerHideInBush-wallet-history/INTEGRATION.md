tier: T2
target: rustchain
language: python
endpoints_used: ["/health", "/wallet/history"]
wallet: RTCe0961d6b54f2fa96db57a373c84d8ad8986153f8
starred: yes

# RustChain Wallet History Verifier

This integration reads live RustChain node state and verifies a wallet's transfer
history response. It is a T2 verification integration because it does more than
render endpoint output:

- confirms the node health endpoint returns `ok: true`
- confirms `/wallet/history` echoes the requested RTC wallet/miner id
- verifies every returned transaction has a numeric amount, a known status, and
  a 32-character hex transaction hash
- totals pending transfer-in rows so an agent can compare public wallet history
  against expected paid-pending bounty records

No private key, seed phrase, wallet password, API secret, or transaction signing
is required. The script performs read-only public HTTP requests.

Run:

```bash
python integrations/FakerHideInBush-wallet-history/wallet_history_verifier.py \
  --miner-id RTCe0961d6b54f2fa96db57a373c84d8ad8986153f8
```

The default node is `https://50.28.86.131`, which is the live node endpoint used
by current RustChain wallet payout checks.
