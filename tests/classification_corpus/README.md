# Classification Test + Fuzz Suite for RustChain

**Bounty:** #16257 (25 RTC)

## Overview

This test suite provides comprehensive test coverage for the node's x86/device
architecture classification path (`cpu_architecture_detection.py`,
`cpu_vintage_architectures.py`, and `node/arch_cross_validation.py`).

## What's Included

### Real-world Corpus (≥30 samples)

| File | Samples | Description |
|------|---------|-------------|
| `vintage_x86_samples.json` | 9 | i486, Pentium, AMD K6, Pentium II/III/4, Athlon XP/64, Phenom II |
| `modern_x86_samples.json` | 10 | Sandy Bridge → Raptor Lake, Xeon servers, Ryzen/EPYC, FX |
| `arm_sbc_samples.json` | 4 | Raspberry Pi 4/5, Orange Pi 5, Jetson Nano |
| `powerpc_samples.json` | 4 | PowerPC G3/G4/G5, AmigaOne |
| `vm_qemu_samples.json` | 6 | QEMU/KVM, VMware, VirtualBox, WSL2, Docker |
| `adversarial_samples.json` | 14 | Empty brand, ARM+x86, family-6+PentiumIII, legacy keys (#7991), unicode, oversized, null-byte, cross-arch spoofs |

**Total:** 47 samples

### Tests

- **`TestCorpusClassification`** — pytest tests that verify each corpus
  sample classifies as expected using the actual detection code
- **`TestClassificationFuzz`** — hypothesis property-based tests:
  - Random brand strings never crash classification
  - Multiplier calculation never crashes
  - No multiplier > 1.0 without vintage evidence
  - Vintage brands always get bonus
  - Short/truncated ASCII strings are handled
  - Dict-shaped inputs to arch_cross_validation are safe
  - **Issue #7991 legacy key name trap** has explicit coverage

### Running

```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run all classification tests
pytest tests/test_classification_corpus_and_fuzz.py -v --tb=short

# Run only fuzz tests (hypothesis)
pytest tests/test_classification_corpus_and_fuzz.py -v -k fuzz

# Run only corpus tests
pytest tests/test_classification_corpus_and_fuzz.py -v -k corpus

# Run specific adversarial test (legacy key name trap)
pytest tests/test_classification_corpus_and_fuzz.py -v -k 7991
```

### Corpus Structure

Each sample in the corpus JSON files follows this schema:

```json
{
  "label": "unique_test_label",
  "description": "Human-readable description with source citation",
  "device_payload": {
    "cpu_family": "6",
    "cpu_brand": "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz",
    "machine": "x86_64",
    "arch_features": {
      "simd_type": "avx",
      "has_sse": true,
      ...
    },
    "cache": {"L1": {"size_kb": 64, "present": true}, ...},
    "clock_drift_cv": 0.002,
    "thermal_drift_pct": 2.0
  },
  "expected": {
    "vendor": "intel",
    "architecture": "sandy_bridge",
    "is_server": false
  }
}
```

### Issue #7991 Coverage

The adversarial corpus includes a sample `legacy_key_name_trap_7991` that
tests the scenario where `cpu_brand` is empty but legacy key names
(`brand_string`, `model_name`) are populated. This reproduces the entropy
profile hash bug where 7 of 9 fields were dead defaults.

### Sources

- Real `/proc/cpuinfo` dumps from preserved vintage hardware
- RustChain vintage-x86 miner honest-classification table
- Intel/AMD CPU microarchitecture timeline (Wikipedia)
- Issue #7991: entropy profile hash reads legacy key names