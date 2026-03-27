# Red Team: Hardware Fingerprint Replay & Spoofing — Security Report

**Bounty:** #248 — Hardware Fingerprint Replay & Spoofing (100 RTC)  
**Target:** RIP-PoA fingerprint attestation system  
**Scope:** Replay (50 RTC) + Clock Drift Spoofing (25 RTC) + Anti-Emulation Bypass (25 RTC)

## Executive Summary

The RIP-PoA hardware fingerprint system has a **fundamental architectural flaw**: all 6 fingerprint checks run client-side and results are self-reported as a JSON dict. The server's `record_fleet_signals_from_request()` accepts this dict without any verification, challenge-response binding, or cryptographic attestation.

**All three attack vectors succeed with trivial effort.**

## Attack 1: Fingerprint Replay (50 RTC)

### Vulnerability

The miner's `_run_fingerprint_checks()` collects hardware measurements locally and stores them in `self.fingerprint_data`. This dict is sent to the server as-is. There is no:
- Challenge-response nonce binding the measurement to a specific attestation
- Server-side re-measurement or verification
- Cryptographic signature proving when/where measurements were taken

### Attack

1. Run miner once on real vintage hardware (e.g., G4 Mac)
2. Save the fingerprint JSON: `json.dump(self.fingerprint_data, open("fp.json", "w"))`
3. On any machine (VM, cloud, modern x86), replace `_run_fingerprint_checks()`:
   ```python
   def _run_fingerprint_checks(self):
       self.fingerprint_data = json.load(open("fp.json"))
       self.fingerprint_passed = True
   ```
4. The server accepts the replayed fingerprint

### Impact

- **Severity: CRITICAL** — Completely defeats hardware authenticity verification
- An attacker can clone one real machine's identity across unlimited VMs
- All fleet detection based on fingerprint similarity becomes meaningless against replayed fingerprints (attacker can add jitter to avoid exact-match detection)

### Evidence

```
[ATTACK 1] Fingerprint Replay
  Captured fingerprint with 6 checks
  Replayed from file — all_passed: True
  ⚠️  Server accepts replayed data — no challenge-response binding
```

21 automated tests confirm all attacks succeed.

## Attack 2: Clock Drift Spoofing (25 RTC)

### Vulnerability

The clock drift check (`check_clock_drift()`) measures oscillator variance and reports a coefficient of variation (CV). The check only rejects:
- `cv < 0.0001` (perfectly uniform = synthetic)
- `drift_stdev == 0` (zero drift = impossible on real hardware)

The CV value is entirely self-reported. An attacker doesn't need to measure real hardware — they can generate synthetic timing data with any desired CV.

### Attack

```python
def spoof_clock_drift(target_cv=0.025, samples=200):
    base_mean = 140000  # Realistic mean_ns
    target_stdev = base_mean * target_cv
    intervals = [random.gauss(base_mean, target_stdev) for _ in range(samples)]
    # Compute stats identical to real check
    cv = stdev(intervals) / mean(intervals)
    # Always passes: cv > 0.0001 and drift_stdev > 0
```

### Results

| Target CV | Actual CV | Passes Check |
|-----------|-----------|:---:|
| 0.010 | 0.010421 | ✅ |
| 0.025 | 0.025847 | ✅ |
| 0.040 | 0.039912 | ✅ |
| 0.060 | 0.061503 | ✅ |
| 0.100 | 0.098719 | ✅ |

### Impact

- **Severity: HIGH** — Attacker can impersonate any CPU's clock characteristics
- Combined with replay attack, can fabricate any hardware profile

## Attack 3: Anti-Emulation Bypass (25 RTC)

### Vulnerability

The `check_anti_emulation()` function runs 4 categories of checks:
1. DMI string matching against VM vendor names
2. Cloud metadata endpoint (169.254.169.254) reachability
3. Hypervisor CPUID flag detection
4. dmesg scanning for VM-related messages

**All checks run on the local machine** — an attacker with root access can mask every indicator.

### Bypass Techniques

| Technique | Difficulty | Method |
|-----------|:---:|--------|
| DMI Masking | Trivial | `mount -t tmpfs tmpfs /sys/class/dmi/id/; echo 'Dell Inc.' > sys_vendor` |
| Metadata Blocking | Trivial | `iptables -A OUTPUT -d 169.254.169.254 -j DROP` |
| CPUID Masking | Easy | KVM: `-cpu host,-hypervisor`; VBox: `--paravirtprovider none` |
| dmesg Filtering | Trivial | `dmesg -C` or `sysctl -w kernel.dmesg_restrict=1` |
| Process Masking | Trivial | `systemctl mask vboxadd.service vmtoolsd.service` |

### Impact

- **Severity: HIGH** — VM farm operators can hide all virtualization indicators
- Every bypass is a single command, automatable in a setup script
- Cloud providers can be masked just as easily as local VMs

## Root Cause Analysis

The fundamental issue is **trust model**: the system trusts the client to honestly report hardware measurements. This is equivalent to asking "are you a robot?" and trusting the answer.

```
Current flow:
  Miner → [runs checks locally] → [sends JSON dict] → Server accepts

No verification:
  ❌ No server-side challenge (nonce) binding measurement to attestation
  ❌ No cryptographic proof of measurement timing/location
  ❌ No remote attestation (TPM, SGX, or equivalent)
  ❌ No statistical anomaly detection on submitted values
```

## Recommended Mitigations

### Short-term (minimal code change)

1. **Server-side nonce in fingerprint**: Server sends a random nonce with each attestation request. Miner must include the nonce in timing measurements (e.g., hash the nonce into the SHA256 loop). Server verifies the nonce is embedded in results.

2. **Statistical anomaly detection**: Track fingerprint history per miner. Flag miners whose clock_drift CV is suspiciously consistent across epochs (real hardware varies).

3. **Fingerprint diversity requirement**: If 10 miners all submit identical fingerprints, penalize — but this is already partially covered by fleet detection.

### Medium-term (moderate effort)

4. **Interactive challenge-response**: Server sends a unique computation challenge. Miner must solve it and submit both the answer and timing data. Different hardware produces measurably different timing patterns for the same challenge.

5. **Temporal binding**: Server records wall-clock time of attestation request. Miner must prove measurements were taken within a narrow window (e.g., fingerprint includes server timestamp hash).

### Long-term (architectural)

6. **Hardware attestation**: Integrate TPM 2.0 quotes or Apple Secure Enclave attestation where available. This provides cryptographic proof of hardware identity.

7. **Proof-of-Work fingerprinting**: Design computation challenges that produce hardware-specific performance signatures that can't be replayed (similar to how Monero's RandomX is ASIC-resistant).

---

**PoC:** `tools/rip_poa_fingerprint_replay_poc.py`  
**Tests:** `tests/test_fingerprint_replay.py` (21 tests)

**Author:** B1tor  
**PAYOUT:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
