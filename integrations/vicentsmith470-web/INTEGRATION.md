tier: T2
target: rustchain
language: Python
endpoints_used: ["/health", "/wallet/balance", "/api/tokenomics"]
wallet: RTCf69dd944558d4e843a4a676495a97638055caea2
starred: yes

# RustChain Wallet Supply Verifier

This integration is a read-only Python verifier for live RustChain nodes. It
checks node health, then verifies two public accounting invariants from live
responses:

- `/wallet/balance` echoes the requested miner/wallet id and keeps `amount_i64`
  consistent with `amount_rtc` in micro-RTC units.
- `/api/tokenomics` keeps `total_supply_urtc` consistent with
  `total_supply_rtc` in micro-RTC units.

Run:

```bash
python integrations/vicentsmith470-web/rustchain_wallet_supply_verifier.py --miner-id RTCf69dd944558d4e843a4a676495a97638055caea2
```

## Live transcript

```text
RustChain wallet supply verifier
health: ok=True version=2.2.1-rip200 tip_age_slots=0
balance: miner=RTCf69dd944558d4e843a4a676495a97638055caea2 amount_i64=0 amount_rtc=0.0 verified_micro_units=True
tokenomics: chain_id=rustchain-mainnet-v2 total_supply_rtc=8388608 total_supply_urtc=8388608000000 verified_supply_units=True reference_rate_usd=0.15
verification: PASS - live wallet balance and token supply unit checks succeeded
```
