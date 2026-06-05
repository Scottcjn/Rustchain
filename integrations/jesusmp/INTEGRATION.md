# T1 RustChain Integration - Live Network Status

## Header
```
tier: T1
target: rustchain
language: python
endpoints_used: [/api/miners, /api/tokenomics]
wallet: jesusmp
starred: yes
```

## What it does
Queries the live RustChain API endpoints and renders a human-readable network status report:
- `/api/miners` - List of active miners with hardware info and last attestation time
- `/api/tokenomics` - Token allocation breakdown

## How to run
```bash
python3 integrations/jesusmp/rustchain_status.py
```

For JSON output:
```bash
python3 integrations/jesusmp/rustchain_status.py --json
```

## Live transcript
```
======================================================================
  RustChain Live Network Status
======================================================================

📡 Fetching live miner data...
  ✅ Active miners: 15

  Miner ID                                 Hardware                  Last Attest
  ---------------------------------------- ------------------------- ---------------
  modern-sophiacore-3a168058               x86-64 (Modern)          2026-06-03 18:35
  ...

📊 Fetching tokenomics data...
  ✅ Tokenomics loaded
  - block_mining: 7,885,291.52 RTC (94.0%)
  - premine: 125,829.12 RTC (1.5%)

======================================================================
  Source: https://rustchain.org
  Integration by: jesusmp
======================================================================
```

## Files
- `rustchain_status.py` - Main script
- `INTEGRATION.md` - This file
