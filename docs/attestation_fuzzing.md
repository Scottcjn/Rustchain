# Attestation Fuzz Harness

This repository includes a deterministic malformed-input fuzz gate for `POST /attest/submit` plus a replayable regression corpus under `tests/attestation_corpus/`.

## Corpus Classes

Current explicit corpus entries cover these malformed input classes:

1. Invalid JSON root: `null`
2. Invalid JSON root: array
3. Miner identifier shape mismatch
4. Device payload scalar/object mismatch
5. Signals payload scalar/object mismatch
6. Signals MAC list shape mismatch
7. Fingerprint checks array/object mismatch
8. Report payload scalar/object mismatch

## Replay One Corpus Entry

```bash
python tests/replay_attestation_corpus.py tests/attestation_corpus/malformed_report_scalar.json
```

The script prints the HTTP status code and parsed JSON response, and exits non-zero if replay causes a server-side `5xx`.

## Quick Regression Gate

```bash
python -m pytest tests/test_attestation_fuzz.py -v
```

## 10,000-Case Fuzz Run

PowerShell:

```powershell
$env:ATTEST_FUZZ_CASES = "10000"
python -m pytest tests/test_attestation_fuzz.py -k fuzz_no_unhandled_exceptions -v
```

Bash:

```bash
ATTEST_FUZZ_CASES=10000 python -m pytest tests/test_attestation_fuzz.py -k fuzz_no_unhandled_exceptions -v
```

This is the CI-mode gate for "no unhandled exceptions" in the attestation parsing path. The command returns non-zero on regression.

Observed local run on Windows / Python 3.14:

- `10,000` generated cases
- `1 passed in 250.90s`
