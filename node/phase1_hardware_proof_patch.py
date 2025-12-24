#!/usr/bin/env python3
"""
Phase 1: Hardware Proof Integration (Logging Only)
===================================================

This patch adds hardware proof validation to /attest/submit but ONLY LOGS results.
It does NOT reject any attestations - fully backwards compatible.

Apply with:
    python3 phase1_hardware_proof_patch.py /root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py
"""

import sys
import re

def apply_patch(filepath):
    print(f"[PATCH] Reading {filepath}...")
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Add import at top (after other imports)
    import_section = '''import secrets
import sqlite3'''

    new_import = '''import secrets
import sqlite3
# Phase 1: Hardware Proof Validation (Logging Only)
try:
    from rip_proof_of_antiquity_hardware import server_side_validation, calculate_entropy_score
    HW_PROOF_AVAILABLE = True
    print("[INIT] Hardware proof validation module loaded")
except ImportError:
    HW_PROOF_AVAILABLE = False
    print("[INIT] WARNING: Hardware proof module not found, using basic validation only")'''

    if 'from rip_proof_of_antiquity_hardware import' not in content:
        content = content.replace(import_section, new_import)
        print("[PATCH] ✓ Added hardware proof import")
    else:
        print("[PATCH] - Hardware proof import already exists")

    # 2. Modify /attest/submit endpoint (find and replace the function)
    attest_pattern = r'(@app\.route\(\'/attest/submit\',.*?methods=\[\'POST\'\]\)\s*def submit_attestation\(\):.*?)(return jsonify\({[^}]*"ok":\s*True[^}]*}\))'

    def attest_replacement(match):
        # Keep everything before the final return
        before_return = match.group(1)

        # Add hardware proof validation before return
        new_code = before_return + '''
    # Phase 1: Hardware Proof Validation (Logging Only - Does NOT reject)
    if HW_PROOF_AVAILABLE:
        try:
            is_valid, proof_result = server_side_validation(data)
            print(f"[HW_PROOF] Miner: {miner}")
            print(f"[HW_PROOF]   Tier: {proof_result.get('antiquity_tier', 'unknown')}")
            print(f"[HW_PROOF]   Multiplier: {proof_result.get('reward_multiplier', 0.0)}")
            print(f"[HW_PROOF]   Entropy: {proof_result.get('entropy_score', 0.0):.3f}")
            print(f"[HW_PROOF]   Confidence: {proof_result.get('confidence', 0.0):.3f}")
            if proof_result.get('warnings'):
                print(f"[HW_PROOF]   Warnings: {proof_result['warnings']}")

            # Phase 1: Accept everyone, just log
            # Phase 2/3 would check: if not is_valid: return jsonify(...), 403
        except Exception as e:
            print(f"[HW_PROOF] ERROR: {e}")

    '''
        # Keep the original return statement
        return new_code + match.group(2)

    if '/attest/submit' in content and 'Phase 1: Hardware Proof Validation' not in content:
        content = re.sub(attest_pattern, attest_replacement, content, flags=re.DOTALL)
        print("[PATCH] ✓ Added hardware proof validation to /attest/submit")
    elif 'Phase 1: Hardware Proof Validation' in content:
        print("[PATCH] - Hardware proof validation already exists")
    else:
        print("[PATCH] ! Could not find /attest/submit endpoint")

    # 3. Write modified content
    print(f"[PATCH] Writing to {filepath}...")
    with open(filepath, 'w') as f:
        f.write(content)

    print("[PATCH] ✅ Phase 1 patch applied successfully!")
    print("[PATCH] Server will now:")
    print("[PATCH]   - Validate all hardware proofs")
    print("[PATCH]   - Log validation results")
    print("[PATCH]   - Accept ALL attestations (backwards compatible)")
    print("[PATCH]")
    print("[PATCH] Next: Restart server and monitor logs for validation results")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 phase1_hardware_proof_patch.py <server_file.py>")
        sys.exit(1)

    apply_patch(sys.argv[1])
