# RustChain T2 Live Balance Verifier

This folder contains a self-contained T2 integration for the RustChain bounty
program. The script reads live RustChain node state and verifies a balance by
checking that:

- the node reports healthy status,
- `slot // blocks_per_epoch == epoch`,
- the selected miner appears in `/api/miners`,
- `/wallet/balance` returns the same miner id, and
- `amount_i64 / 1_000_000` matches `amount_rtc`.

## Requirements

- Python 3.10 or newer
- Network access to a RustChain node
- No third-party Python packages

## Run

From the repository root:

```bash
python integrations/KHHH2312/rustchain_t2_verifier.py --miner-id power8-s824-sophia
```

Optional arguments:

```bash
python integrations/KHHH2312/rustchain_t2_verifier.py --base-url https://rustchain.org
python integrations/KHHH2312/rustchain_t2_verifier.py --miner-id power8-s824-sophia
python integrations/KHHH2312/rustchain_t2_verifier.py --json
```

`--base-url` is validated before use. The script accepts HTTPS endpoints and
local development URLs only, rejects embedded credentials, rejects redirects,
and refuses private or reserved remote addresses.

## Example output

```text
RustChain T2 live verification
health: ok=True version=2.2.1-rip200 tip_age_slots=0
epoch: epoch=182 slot=26348 blocks_per_epoch=144 verified_slot_epoch=True
miners: enrolled_epoch=25 listed=20 selected=power8-s824-sophia selected_is_enrolled=True
balance: miner=power8-s824-sophia amount_i64=89958498 amount_rtc=89.958498 verified_micro_units=True
verification: PASS - live miner enrollment and balance unit checks succeeded
```

## Files

- `INTEGRATION.md` - bounty metadata and live transcript.
- `README.md` - usage and verification notes.
- `TRANSCRIPT.txt` - captured live-node run.
- `rustchain_t2_verifier.py` - integration script.
- `test_rustchain_t2_verifier.py` - standard-library unit tests for the
  verification helpers.
