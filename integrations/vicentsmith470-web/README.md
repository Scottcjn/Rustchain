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

Strict local unit-check examples before the live run:

```bash
python integrations/vicentsmith470-web/rustchain_wallet_supply_verifier.py \
  --miner-id RTCf69dd944558d4e843a4a676495a97638055caea2 \
  --self-test
```

## What It Verifies

- `/health` returns `ok: true`.
- `/wallet/balance` echoes the requested `miner_id`.
- `amount_i64` is an integer micro-unit value and exactly equals
  `amount_rtc * 1_000_000`.
- `/api/tokenomics` reports `total_supply_urtc` equal to
  `total_supply_rtc * 1_000_000`, with no fractional micro-units.
- Local self-test examples reject fractional micro-unit inputs such as
  `amount_rtc=0.0000005`, `amount_i64=1.9`, and
  `total_supply_urtc=1000000.5`.

No private key, seed phrase, wallet export, signing key, admin key, write
endpoint, or transaction action is used.
