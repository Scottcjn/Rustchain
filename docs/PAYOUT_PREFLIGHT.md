# Payout Preflight (Dry-Run Validation)

Goal: payout operations should never return server 500s due to malformed input. This repo includes a small, dependency-light preflight validator to catch bad payloads early and provide predictable 4xx errors.

## What It Covers

- `POST /wallet/transfer` (admin transfer)
  - Rejects malformed JSON bodies (non-object)
  - Rejects missing `from_miner` / `to_miner`
  - Rejects non-numeric, non-finite, or non-positive `amount_rtc`

- `POST /wallet/transfer/signed` (client signed transfer)
  - Rejects malformed JSON bodies (non-object)
  - Rejects missing required fields
  - Rejects non-numeric, non-finite, or non-positive `amount_rtc`
  - Rejects invalid address formats / from==to
  - Rejects invalid/non-positive nonces

Note: this preflight does not replace signature verification or admin-key authorization. It is a guardrail to prevent 500s and to make failure modes consistent.

## CLI Checker

Use the CLI to validate payloads before submitting a payout request:

```bash
python3 tools/payout_preflight_check.py --mode admin --input payload.json
python3 tools/payout_preflight_check.py --mode signed --input payload.json
```

You can also read from stdin:

```bash
cat payload.json | python3 tools/payout_preflight_check.py --mode admin --input -
```

Exit codes:

- `0`: ok
- `1`: invalid payload (preflight failed)
- `2`: invalid JSON parse / unreadable input

