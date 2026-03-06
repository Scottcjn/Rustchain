#!/usr/bin/env python3
"""Add entropy validation to submit_attestation()"""

import re
import sys

def add_entropy_validation(filepath):
    with open(filepath, 'r') as f:
        code = f.read()

    # Check if already added
    if '[HW_PROOF]' in code and 'Entropy:' in code:
        print("ℹ️  Entropy validation already integrated")
        return False

    # Find submit_attestation function
    match = re.search(r'def submit_attestation\(\):', code)
    if not match:
        print("❌ Could not find submit_attestation()")
        return False

    func_start = match.start()

    # Find the final return jsonify with ok: True in this function
    # Look for pattern before the return
    pattern = r'(\s+)(return jsonify\(\{[^}]*["\']ok["\']:\s*True)'

    matches = list(re.finditer(pattern, code[func_start:]))
    if not matches:
        print("❌ Could not find success return in submit_attestation")
        return False

    # Get the last match (final success return)
    last_match = matches[-1]
    insertion_point = func_start + last_match.start()
    indent = last_match.group(1)

    # Add validation code before the return
    validation_code = f'''{indent}# Entropy validation (Phase 1: Warning only)
{indent}entropy_score = 0.0
{indent}if HW_PROOF_AVAILABLE:
{indent}    try:
{indent}        is_valid, proof_result = server_side_validation(data)
{indent}        entropy_score = proof_result.get("entropy_score", 0.0)
{indent}
{indent}        print(f"[HW_PROOF] Miner: {{miner[:20]}}...")
{indent}        print(f"[HW_PROOF]   Entropy: {{entropy_score:.3f}}")
{indent}        print(f"[HW_PROOF]   Tier: {{proof_result.get('antiquity_tier', 'unknown')}}")
{indent}
{indent}        if entropy_score < 0.15:
{indent}            print(f"[ENTROPY] WARNING: LOW ENTROPY {{entropy_score:.3f}} for {{miner[:20]}} - SUSPICIOUS")
{indent}    except Exception as e:
{indent}        print(f"[HW_PROOF] Validation error: {{e}}")

'''

    # Insert the code
    new_code = code[:insertion_point] + validation_code + code[insertion_point:]

    # Write back
    with open(filepath, 'w') as f:
        f.write(new_code)

    print("✅ Added entropy validation to submit_attestation()")
    return True

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py"
    result = add_entropy_validation(filepath)
    sys.exit(0 if result else 1)
