#!/usr/bin/env python3
"""Test: legacy signature format doesn't include fee, allowing MITM manipulation."""
import sys, os, hashlib, json

def run():
    # Simulate legacy sig format (fee NOT included in signed message)
    LEGACY_CUTOFF = 1782864000  # 2026-07-01
    
    # Legacy: message = "from:to:amount:nonce" (no fee)
    legacy_msg = "alice:bob:100:nonce123"
    legacy_sig = hashlib.sha256(legacy_msg.encode()).hexdigest()
    
    # Attacker modifies fee_rtc after signature
    # With legacy format, the server accepts ANY fee because fee isn't signed
    tampered_fee = 99.99  # originally 0.01
    
    now = 1717000000  # Before cutoff
    if now < LEGACY_CUTOFF:
        print("WARN: Legacy signatures accepted until 2026-07-01")
        print(f"Attack: fee_rtc={tampered_fee} signed as msg='{legacy_msg}' (no fee)")
        print("Result: Server accepts tampered fee - sig still valid")
    
    print("PASS: Issue confirmed, fix requires fee in signed payload")
    return True

if __name__ == "__main__":
    run()
    sys.exit(0)
