# Attestation Fuzz Harness — Bounty #475

Property-based fuzz testing for the RustChain `/attest/submit` endpoint validators.

## Overview

This harness targets the attestation validator pipeline extracted from
`node/rustchain_v2_integrated_v2.2.1_rip200.py`. It exercises the validators
directly — no Flask server needed — for fast, deterministic, CI-friendly execution.

### Validators under test

| Function | What it validates |
|---|---|
| `_attest_mapping` | Ensures a value is a dict; returns `{}` otherwise |
| `_attest_text` | Non-empty, stripped string only |
| `_attest_valid_miner` | Miner ID — `[A-Za-z0-9._:-]{1,128}` |
| `_attest_is_valid_positive_int` | Integer 1–4096, rejects bools/floats/overflow |
| `_attest_positive_int` | Safe coercion with configurable default |
| `_attest_string_list` | List of non-empty strings |
| `_validate_attestation_payload_shape` | Full payload shape validation |

---

## Quick Start

```bash
# Install deps
pip install hypothesis pytest

# Full run (corpus + Hypothesis, ≥10,000 cases)
python tests/fuzz/run_fuzz.py

# Corpus-only replay (deterministic, fast, no Hypothesis)
python tests/fuzz/run_fuzz.py --corpus-only

# Run just the harness via pytest
pytest tests/fuzz/attestation_fuzz_harness.py -v

# Deterministic seed (for exact reproduction)
pytest tests/fuzz/attestation_fuzz_harness.py -v --hypothesis-seed=0
```

---

## CI Integration

Add to your CI pipeline (`.github/workflows/fuzz.yml` or similar):

```yaml
- name: Run attestation fuzz harness
  run: python tests/fuzz/run_fuzz.py
```

**Exit codes:**
- `0` — All ≥10,000 cases passed; corpus clean
- `1` — Regression detected or case threshold not met

The runner returns non-zero on any regression, making it safe to gate PRs on.

---

## Crash Classes Covered (≥5 required, 8 implemented)

| # | Class | Description |
|---|---|---|
| 1 | `TYPE_CONFUSION` | Wrong Python type for any sub-object field (list instead of dict, etc.) |
| 2 | `MISSING_FIELDS` | Required keys (`miner`/`miner_id`) absent or `None` |
| 3 | `OVERSIZED_VALUES` | Strings/lists far beyond expected bounds (up to 100 KB) |
| 4 | `BOUNDARY_INTS` | `device.cores` = 0, -1, bool, float, inf, nan, overflow |
| 5 | `NESTED_SHAPE` | `fingerprint.checks` that is a list, string, or integer |
| 6 | `MINER_ID_INJECT` | SQL injection, path traversal, non-ASCII, whitespace in miner ID |
| 7 | `EMPTY_CONTAINERS` | Whitespace-only strings, empty lists, `[]` macs |
| 8 | `MAC_LIST_ABUSE` | `signals.macs` with nulls, ints, nested lists, mixed types |

---

## Regression Corpus

`tests/fuzz/regression_corpus/` contains 8 deterministic JSON fixtures — one per
crash class. Each file carries metadata keys prefixed with `_`:

```json
{
  "_class": "TYPE_CONFUSION",
  "_description": "device field is a list...",
  "_expected_error_code": "INVALID_DEVICE",
  "miner": "valid-miner",
  "device": [1, 2, 3]
}
```

Meta-keys are stripped before the payload reaches the validator.

To add a new regression case, drop a `.json` file into the corpus directory.
The CI runner picks it up automatically on the next run.

---

## How Hypothesis Works Here

The harness uses [Hypothesis](https://hypothesis.readthedocs.io/) strategies
to generate structured, adversarial inputs:

- **10,500+ examples** across all test functions
- **Seeded run** (`seed=0xDEADBEEF`) for deterministic reproduction
- **`deadline=None`** so slow strategies don't mask bugs
- **`suppress_health_check=[too_slow]`** for large composite strategies

Hypothesis stores its database in `.hypothesis/` (git-ignored). Shrunk
counterexamples are saved there so re-running produces the minimal failing case.

---

## Files

```
tests/fuzz/
├── attestation_fuzz_harness.py   # Main harness (Hypothesis)
├── attestation_validators.py     # Extracted validators (no Flask dependency)
├── run_fuzz.py                   # CI runner (corpus + Hypothesis)
├── README.md                     # This file
└── regression_corpus/
    ├── crash_01_type_confusion_device.json
    ├── crash_02_missing_miner.json
    ├── crash_03_invalid_cores_bool.json
    ├── crash_04_miner_id_special_chars.json
    ├── crash_05_nested_fingerprint_checks_not_dict.json
    ├── crash_06_mac_list_with_null.json
    ├── crash_07_oversized_miner_id.json
    └── crash_08_empty_containers.json
```

---

## Bounty Info

- **Bounty:** #475 — Attestation Fuzz Harness + Crash Regression Corpus
- **Author:** @B1tor
- **Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
