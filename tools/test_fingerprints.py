#!/usr/bin/env python3
"""
RustChain Hardware Fingerprint Test Suite
========================================
Bounty #44 Implementation - Preflight Validator
"""

import os
import sys
import json
import time
import platform
import statistics
from typing import Dict, Any, List

# Import existing checks
try:
    import fingerprint_checks
except ImportError:
    print("[!] Error: fingerprint_checks.py not found in current directory.")
    sys.exit(1)

# Reference Profiles (Expected Values)
REFERENCE_PROFILES = {
    "G4": {
        "clock_cv_min": 0.05,
        "clock_cv_max": 0.15,
        "cache_ratio_min": 1.2,
        "jitter_stdev_min": 50
    },
    "G5": {
        "clock_cv_min": 0.04,
        "clock_cv_max": 0.12,
        "cache_ratio_min": 1.5,
        "jitter_stdev_min": 40
    },
    "x86": {
        "clock_cv_min": 0.02,
        "clock_cv_max": 0.10,
        "cache_ratio_min": 2.0,
        "jitter_stdev_min": 20
    }
}

class FingerprintTester:
    def __init__(self):
        self.results = {}
        self.system_info = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "version": platform.version()
        }

    def run_tests(self):
        print("=" * 80)
        print(f"RustChain Hardware Fingerprint Preflight Validator")
        print("=" * 80)
        print(f"System: {self.system_info['platform']} {self.system_info['machine']}")
        print(f"CPU: {self.system_info['processor']}")
        print("-" * 80)

        # 1. Clock-Skew & Oscillator Drift
        self._test_check("clock_drift", "Clock-Skew & Oscillator Drift", fingerprint_checks.check_clock_drift)
        
        # 2. Cache Timing Fingerprint
        self._test_check("cache_timing", "Cache Timing Fingerprint", fingerprint_checks.check_cache_timing)
        
        # 3. SIMD Unit Identity
        self._test_check("simd_identity", "SIMD Unit Identity", fingerprint_checks.check_simd_identity)
        
        # 4. Thermal Drift Entropy
        self._test_check("thermal_drift", "Thermal Drift Entropy", fingerprint_checks.check_thermal_drift)
        
        # 5. Instruction Path Jitter
        self._test_check("instruction_jitter", "Instruction Path Jitter", fingerprint_checks.check_instruction_jitter)
        
        # 6. Anti-Emulation
        self._test_check("anti_emulation", "Anti-Emulation Behavioral Checks", fingerprint_checks.check_anti_emulation)

        self._print_summary()

    def _test_check(self, key: str, name: str, func):
        print(f"[*] Running {name}...")
        try:
            passed, data = func()
            self.results[key] = {"passed": passed, "data": data}
            
            status = "PASS" if passed else "FAIL"
            print(f"    Status: {status}")
            
            # Print diagnostics based on check type
            if key == "clock_drift":
                cv = data.get("cv", 0)
                print(f"    Coefficient of Variation (CV): {cv:.6f} (Min required: 0.0001)")
                if cv < 0.0001: print("    [!] WARNING: Clock too stable! Might be virtualized.")
                
            elif key == "cache_timing":
                l2_l1 = data.get("l2_l1_ratio", 0)
                l3_l2 = data.get("l3_l2_ratio", 0)
                print(f"    L2/L1 Latency Ratio: {l2_l1:.3f}")
                print(f"    L3/L2 Latency Ratio: {l3_l2:.3f}")
                if l2_l1 < 1.05: print("    [!] WARNING: Flat cache hierarchy detected.")
                
            elif key == "simd_identity":
                print(f"    SIMD: SSE={data.get('has_sse')}, AVX={data.get('has_avx')}, AltiVec={data.get('has_altivec')}, NEON={data.get('has_neon')}")
                
            elif key == "anti_emulation":
                indicators = data.get("vm_indicators", [])
                if indicators:
                    print(f"    [!] VM Indicators Found: {', '.join(indicators)}")
                else:
                    print(f"    No VM indicators found.")
            
            print()
        except Exception as e:
            print(f"    [!] ERROR: {e}")
            self.results[key] = {"passed": False, "error": str(e)}

    def _print_summary(self):
        all_passed = all(r.get("passed", False) for r in self.results.values())
        
        print("-" * 80)
        print(f"TEST SUMMARY: {'PASSED' if all_passed else 'FAILED'}")
        print("-" * 80)
        
        if all_passed:
            print("Congratulations! Your hardware fingerprint matches real-silicon characteristics.")
            print("Your miner is likely to receive maximum antiquity multipliers.")
        else:
            failed = [k for k, v in self.results.items() if not v.get("passed")]
            print(f"Failed checks: {', '.join(failed)}")
            print("\nActionable Recommendations:")
            if "clock_drift" in failed or "instruction_jitter" in failed:
                print("- Check if your OS is running inside a VM (VirtualBox, VMware, etc).")
                print("- Ensure CPU frequency scaling isn't masking timing variance.")
            if "cache_timing" in failed:
                print("- This check requires stable cache behavior. Close high-memory background apps.")
            if "anti_emulation" in failed:
                print("- Review the VM indicators listed in the diagnostic section above.")
        
        print("\n" + "=" * 80)

    def export_json(self, filename: str = "fingerprint_results.json"):
        export_data = {
            "system": self.system_info,
            "timestamp": int(time.time()),
            "results": self.results
        }
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        print(f"[*] Results exported to {filename}")

if __name__ == "__main__":
    tester = FingerprintTester()
    tester.run_tests()
    tester.export_json()
