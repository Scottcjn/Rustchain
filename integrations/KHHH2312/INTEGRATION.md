tier: T2
target: rustchain
language: Python
endpoints_used: ["/health", "/epoch", "/api/miners", "/wallet/balance"]
wallet: RTCa131d459d440c4c6bef6d69803db2cab0c696a34
starred: yes

# RustChain Live Balance Verifier

This integration is a small Python command-line verifier for live RustChain
nodes. It performs the T1 read checks, then verifies live chain state by
cross-checking the enrolled miner list against a wallet balance lookup.

The verifier uses the public node by default:

```bash
python integrations/KHHH2312/rustchain_t2_verifier.py --miner-id power8-s824-sophia
```

It reads:

- `/health` to confirm the node is healthy.
- `/epoch` to verify the slot-to-epoch relationship.
- `/api/miners` to select or confirm an enrolled miner.
- `/wallet/balance` to verify that the live balance response matches the
  selected miner and that `amount_i64` is consistent with `amount_rtc`.

## Live transcript

```text
RustChain T2 live verification
health: ok=True version=2.2.1-rip200 tip_age_slots=0
epoch: epoch=182 slot=26348 blocks_per_epoch=144 verified_slot_epoch=True
miners: enrolled_epoch=25 listed=20 selected=power8-s824-sophia selected_is_enrolled=True
balance: miner=power8-s824-sophia amount_i64=89958498 amount_rtc=89.958498 verified_micro_units=True
verification: PASS - live miner enrollment and balance unit checks succeeded
```
