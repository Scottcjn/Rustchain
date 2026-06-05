# RustChain Wallet Supply Verifier

Read-only T2 integration for RustChain bounty #13040. The verifier calls the
live RustChain node and checks that public wallet and tokenomics responses are
internally consistent.

## Run

```bash
python integrations/vicentsmith470-web/rustchain_wallet_supply_verifier.py \
  --miner-id RTCf69dd944558d4e843a4a676495a97638055caea2
```

Optional JSON output:

```bash
python integrations/vicentsmith470-web/rustchain_wallet_supply_verifier.py \
  --miner-id RTCf69dd944558d4e843a4a676495a97638055caea2 \
  --json
```

## What It Verifies

- `/health` returns `ok: true`.
- `/wallet/balance` echoes the requested `miner_id`.
- `amount_i64` equals `amount_rtc * 1_000_000`.
- `/api/tokenomics` reports `total_supply_urtc` equal to
  `total_supply_rtc * 1_000_000`.

No private key, seed phrase, wallet export, signing key, admin key, write
endpoint, or transaction action is used.
