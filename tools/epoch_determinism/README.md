# Epoch Determinism Simulator + Cross-Node Replay

**Bounty #474** — Proves that epoch settlement outputs are byte-equivalent across
nodes for identical fixture inputs.

---

## Overview

The replay harness loads a JSON fixture (encoding epoch state and miner
attestations), spins up two independent in-memory SQLite databases (simulating
two different nodes), runs the same settlement logic against both, and compares
the resulting payout maps.

If both nodes produce the **same canonical hash** over the sorted payout dict,
the epoch settlement is deterministic. Any divergence is reported per-miner and
the tool exits `1`.

---

## Quick Start (one-command)

```bash
# From repo root:
python tools/epoch_determinism/replay.py tools/epoch_determinism/fixtures/normal_epoch.json
```

Expected output:
```
[replay] fixture='normal_epoch' epoch=10 targets=['node_a', 'node_b']
[replay] ✅ DETERMINISTIC MATCH  hash=<first-16-chars>…
```

---

## Installation

No extra dependencies beyond Python ≥ 3.8 and the repo itself.

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python tools/epoch_determinism/replay.py tools/epoch_determinism/fixtures/normal_epoch.json
```

---

## CLI Reference

```
usage: replay.py <fixture.json> [options]

positional arguments:
  fixture               Path to JSON fixture file

options:
  --targets A B         Names for the two simulated nodes
                        (default: node_a node_b)
  --report-json FILE    Save full JSON report to FILE
  --report-md           Print markdown summary to stdout
  --ci                  Exit 1 on mismatch (for CI pipelines)
  --verbose, -v         Print full JSON report to stdout

Exit codes:
  0   outputs are byte-equivalent (deterministic)
  1   mismatch detected, or fixture load error
```

### Examples

```bash
# Basic determinism check
python tools/epoch_determinism/replay.py fixtures/normal_epoch.json

# Named targets
python tools/epoch_determinism/replay.py fixtures/sparse_epoch.json \
    --targets primary_node secondary_node

# Save report
python tools/epoch_determinism/replay.py fixtures/edge_case_epoch.json \
    --report-json /tmp/report.json --report-md

# CI mode — divergent fixture must exit 1
python tools/epoch_determinism/replay.py fixtures/divergent_epoch.json --ci
echo "Exit: $?"  # → 1
```

---

## Fixture Format

Fixtures are JSON files in `fixtures/`. Each fixture describes one epoch's
worth of miner attestation data and optional enrollment overrides.

### Schema

```json
{
  "fixture_id":   "string (unique, slug)",
  "description":  "string",
  "epoch":        0,
  "miners": [
    {
      "miner_id":          "RTC…",
      "device_arch":       "g4|modern|486|68000|…",
      "ts_offset":         100,
      "fingerprint_passed": 1,
      "warthog_bonus":      1.0
    }
  ],

  // Optional: use epoch_enroll primary path instead of miner_attest_recent
  "epoch_enroll_override": [
    { "miner_pk": "RTC…", "weight": 2.5 }
  ],

  // Optional: flag for divergence injection in tests
  "inject_divergence": false
}
```

### Field reference

| Field | Required | Description |
|---|---|---|
| `fixture_id` | ✅ | Unique slug |
| `description` | ✅ | Human-readable description |
| `epoch` | ✅ | Epoch number to simulate |
| `miners` | ✅ | List of miner attestation entries |
| `miners[].miner_id` | ✅ | Wallet address (`RTC…`) |
| `miners[].device_arch` | ✅ | Architecture key (see `ANTIQUITY_MULTIPLIERS`) |
| `miners[].ts_offset` | — | Seconds after epoch start (default 100) |
| `miners[].fingerprint_passed` | — | 0 = failed (no reward), 1 = pass (default 1) |
| `miners[].warthog_bonus` | — | Warthog dual-mining bonus ×1.0/1.1/1.15 (default 1.0) |
| `epoch_enroll_override` | — | If present: uses `epoch_enroll` primary path |
| `inject_divergence` | — | If true: test harness injects deliberate divergence |

---

## Settlement Paths

The simulator replicates two code paths from the production node:

### Primary: `epoch_enroll`
When `epoch_enroll_override` is present in the fixture, rewards are distributed
proportionally to explicit `weight` values stored in the `epoch_enroll` table.
This is the primary enrollment path used in production.

### Fallback: `miner_attest_recent`
When no `epoch_enroll_override` is present, the standard
`calculate_epoch_rewards_time_aged()` function queries `miner_attest_recent` for
all miners attested during the epoch window, applies time-aged antiquity
multipliers, and distributes rewards proportionally.

---

## Included Fixtures

| Fixture | Path | Description |
|---|---|---|
| `normal_epoch` | `fixtures/normal_epoch.json` | 5 miners, mixed tiers, standard operation |
| `sparse_epoch` | `fixtures/sparse_epoch.json` | 2 miners only (ancient + modern) |
| `edge_case_epoch` | `fixtures/edge_case_epoch.json` | Fingerprint failure + epoch_enroll path |
| `divergent_epoch` | `fixtures/divergent_epoch.json` | Intentionally divergent — mismatch expected |

---

## Report Output

### JSON Report (`--report-json`)

```json
{
  "fixture_id": "normal_epoch",
  "description": "...",
  "epoch": 10,
  "determinism_ok": true,
  "targets": ["node_a", "node_b"],
  "canonical_hashes": {
    "node_a": "abc123...",
    "node_b": "abc123..."
  },
  "total_urtc": { "node_a": 1500000, "node_b": 1500000 },
  "payouts": {
    "node_a": { "RTC1...": 450000, "RTC2...": 1050000 },
    "node_b": { "RTC1...": 450000, "RTC2...": 1050000 }
  },
  "diffs": [],
  "elapsed_s": 0.012,
  "generated_at": "2026-03-27T00:00:00Z"
}
```

On mismatch, `diffs` contains per-miner divergence:
```json
"diffs": [
  {
    "miner_id": "RTC...",
    "node_a": 450000,
    "node_b": 517500,
    "delta_urtc": 67500
  }
]
```

### Markdown Report (`--report-md`)

Prints a human-readable summary with canonical hash table, payout table,
and per-miner diff list. Suitable for PR descriptions and CI logs.

---

## Running Tests

```bash
# All epoch-determinism tests
python -m pytest tests/test_epoch_determinism.py -v

# With coverage
python -m pytest tests/test_epoch_determinism.py -v --tb=short

# Single test
python -m pytest tests/test_epoch_determinism.py::test_divergent_detects_mismatch -v
```

Expected: 5 tests pass (including `test_divergent_detects_mismatch` which
intentionally expects exit code 1).

---

## Determinism Guarantee

The replay tool guarantees determinism by:

1. **Identical inputs**: Both nodes receive the same fixture data loaded into
   fresh, identically-structured SQLite databases.

2. **Canonical ordering**: Payout dicts are sorted by `miner_id` before hashing.

3. **Integer arithmetic**: Rewards stored as integer uRTC (no float drift).

4. **Last-miner remainder**: The final miner absorbs any rounding residual,
   ensuring `sum(payouts) == PER_EPOCH_URTC` exactly.

5. **Byte-equivalent comparison**: SHA-256 over `json.dumps(payouts, sort_keys=True)`.

---

## Reproduction Steps

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
git checkout scottcjn/epoch-determinism-474

# Run all fixtures
for f in tools/epoch_determinism/fixtures/normal_epoch.json \
          tools/epoch_determinism/fixtures/sparse_epoch.json \
          tools/epoch_determinism/fixtures/edge_case_epoch.json; do
    python tools/epoch_determinism/replay.py "$f"
done

# Divergent fixture — expect exit code 1
python tools/epoch_determinism/replay.py \
    tools/epoch_determinism/fixtures/divergent_epoch.json \
    --ci || echo "Mismatch correctly detected (expected)"

# Run tests
python -m pytest tests/test_epoch_determinism.py -v
```
