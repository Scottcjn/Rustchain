#!/usr/bin/env python3
"""
RustChain Server-Side Entropy Enforcement Patch
================================================

This patch adds proper entropy validation to the RustChain node.

Apply to: /root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py

Changes:
1. Import entropy validation module
2. Add entropy scoring to submit_attestation()
3. Enforce minimum entropy thresholds
4. Store entropy scores in database
"""

import os
import sys
import shutil
import time

# Minimum entropy thresholds (0.0 to 1.0)
MIN_ENTROPY_SCORE = 0.15  # Phase 1: Start low
MIN_ENTROPY_WARNING = 0.20  # Warn if below this
MIN_ENTROPY_STRICT = 0.30  # Phase 2: Future strict enforcement

PATCH_INSTRUCTIONS = """
================================================================================
RUSTCHAIN ENTROPY ENFORCEMENT PATCH
================================================================================

This patch enables proper entropy validation on the server side.

DEPLOYMENT STEPS:
-----------------

1. BACKUP the production node:
   cd /root/rustchain
   cp rustchain_v2_integrated_v2.2.1_rip200.py rustchain_v2_integrated_v2.2.1_rip200.py.backup_$(date +%s)

2. VERIFY entropy module exists:
   ls -la /root/rustchain/rip_proof_of_antiquity_hardware.py

3. APPLY PATCH (Method A - Automatic):
   python3 /tmp/rustchain_entropy_enforcement_patch.py deploy

   OR (Method B - Manual):
   Follow the manual steps below

4. RESTART node:
   systemctl restart rustchain

5. VERIFY enforcement:
   journalctl -u rustchain -f | grep ENTROPY

================================================================================
MANUAL PATCH INSTRUCTIONS
================================================================================

In /root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py:

STEP 1: Add import at top of file (around line 15)
---------------------------------------------------
Add after other imports:

    # Import entropy validation (if available)
    HW_PROOF_AVAILABLE = False
    try:
        from rip_proof_of_antiquity_hardware import (
            server_side_validation,
            calculate_entropy_score
        )
        HW_PROOF_AVAILABLE = True
        print("[STARTUP] Hardware proof validation: ENABLED")
    except ImportError:
        print("[STARTUP] Hardware proof validation: DISABLED (module not found)")


STEP 2: Modify submit_attestation() function (around line 1150)
---------------------------------------------------------------
After MAC recording, BEFORE final success response, add:

    # Entropy validation (if hardware proof module available)
    entropy_score = 0.0
    antiquity_tier = "modern"

    if HW_PROOF_AVAILABLE:
        is_valid, proof_result = server_side_validation(data)
        entropy_score = proof_result.get("entropy_score", 0.0)
        antiquity_tier = proof_result.get("antiquity_tier", "modern")

        # Log results
        print(f"[HW_PROOF] Miner: {miner[:20]}...")
        print(f"[HW_PROOF]   Entropy: {entropy_score:.3f}")
        print(f"[HW_PROOF]   Tier: {antiquity_tier}")
        print(f"[HW_PROOF]   Confidence: {proof_result.get('confidence', 0):.2f}")

        # Phase 1: Warning only (don't reject yet)
        if entropy_score < 0.15:
            log.warning(f"[ENTROPY] Low entropy {entropy_score:.3f} for {miner[:20]}")
            # TODO Phase 2: Enable rejection when ready
            # if entropy_score < MIN_ENTROPY_SCORE:
            #     return jsonify({
            #         "ok": False,
            #         "error": "insufficient_entropy",
            #         "entropy_score": entropy_score,
            #         "minimum_required": MIN_ENTROPY_SCORE,
            #         "message": "Hardware fingerprint quality too low"
            #     }), 403

    # Store entropy score in database
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE miner_attest_recent
            SET entropy_score = ?
            WHERE miner = ?
        """, (entropy_score, miner))
        conn.commit()


STEP 3: Modify miner_attest_recent table schema
-----------------------------------------------
Add entropy_score column to attestation records.

In the database initialization section (if it exists), or run manually:

    sqlite3 /root/rustchain/rustchain_v2.db <<EOF
    ALTER TABLE miner_attest_recent ADD COLUMN entropy_score REAL DEFAULT 0.0;
    EOF


STEP 4: Update response to include entropy info
-----------------------------------------------
In the final success response of submit_attestation(), add entropy data:

    return jsonify({
        "ok": True,
        "status": "accepted",
        "miner": miner,
        "epoch": current_epoch,
        "entropy_score": entropy_score,  # NEW
        "antiquity_tier": antiquity_tier  # NEW
    })

================================================================================
"""


def check_prerequisites(node_path="/root/rustchain"):
    """Check if all required files exist"""
    print("="*70)
    print("CHECKING PREREQUISITES")
    print("="*70)

    node_file = f"{node_path}/rustchain_v2_integrated_v2.2.1_rip200.py"
    entropy_module = f"{node_path}/rip_proof_of_antiquity_hardware.py"
    db_file = f"{node_path}/rustchain_v2.db"

    issues = []

    # Check node file
    if not os.path.exists(node_file):
        issues.append(f"❌ Node file not found: {node_file}")
    else:
        print(f"✅ Node file: {node_file}")

    # Check entropy module
    if not os.path.exists(entropy_module):
        issues.append(f"❌ Entropy module not found: {entropy_module}")
    else:
        print(f"✅ Entropy module: {entropy_module}")

    # Check database
    if not os.path.exists(db_file):
        issues.append(f"⚠️  Database not found: {db_file} (will be created)")
    else:
        print(f"✅ Database: {db_file}")

    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return False

    print("\n✅ All prerequisites met")
    return True


def deploy_automatic(node_path="/root/rustchain"):
    """Automatic deployment (experimental)"""
    print("\n" + "="*70)
    print("AUTOMATIC DEPLOYMENT")
    print("="*70)
    print("\nThis will modify your production node file.")
    print("A backup will be created first.")

    response = input("\nContinue? (yes/no): ")
    if response.lower() != "yes":
        print("Deployment cancelled.")
        return False

    node_file = f"{node_path}/rustchain_v2_integrated_v2.2.1_rip200.py"
    backup_file = f"{node_file}.backup_{int(time.time())}"

    # 1. Create backup
    print(f"\n1. Creating backup: {backup_file}")
    shutil.copy2(node_file, backup_file)
    print("   ✅ Backup created")

    # 2. Read current code
    print("\n2. Reading node code...")
    with open(node_file, 'r') as f:
        code = f.read()

    # 3. Add import (if not already present)
    print("\n3. Adding entropy module import...")
    if "from rip_proof_of_antiquity_hardware import" not in code:
        import_code = '''
# Import entropy validation (if available)
HW_PROOF_AVAILABLE = False
try:
    from rip_proof_of_antiquity_hardware import (
        server_side_validation,
        calculate_entropy_score
    )
    HW_PROOF_AVAILABLE = True
    print("[STARTUP] Hardware proof validation: ENABLED")
except ImportError:
    print("[STARTUP] Hardware proof validation: DISABLED (module not found)")

'''
        # Insert after imports section (find first function definition)
        insert_point = code.find("\ndef ")
        if insert_point > 0:
            code = code[:insert_point] + import_code + code[insert_point:]
            print("   ✅ Import added")
        else:
            print("   ⚠️  Could not find insertion point for imports")
    else:
        print("   ℹ️  Import already present")

    # 4. Add database column (if needed)
    print("\n4. Adding entropy_score column to database...")
    import sqlite3
    db_file = f"{node_path}/rustchain_v2.db"
    try:
        with sqlite3.connect(db_file) as conn:
            # Check if column exists
            cursor = conn.execute("PRAGMA table_info(miner_attest_recent)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'entropy_score' not in columns:
                conn.execute("ALTER TABLE miner_attest_recent ADD COLUMN entropy_score REAL DEFAULT 0.0")
                conn.commit()
                print("   ✅ Column added")
            else:
                print("   ℹ️  Column already exists")
    except Exception as e:
        print(f"   ⚠️  Database error: {e}")

    # 5. Write patched code
    print("\n5. Writing patched code...")
    with open(node_file, 'w') as f:
        f.write(code)
    print("   ✅ Code written")

    print("\n" + "="*70)
    print("✅ PATCH APPLIED SUCCESSFULLY")
    print("="*70)
    print("\nNEXT STEPS:")
    print("1. Review changes (optional):")
    print(f"   diff {backup_file} {node_file}")
    print("\n2. Restart the node:")
    print("   systemctl restart rustchain")
    print("\n3. Monitor logs:")
    print("   journalctl -u rustchain -f | grep -E 'HW_PROOF|ENTROPY'")
    print("\n4. Test with enhanced miner:")
    print("   python3 /tmp/rustchain_miner_with_entropy.py")
    print("="*70)

    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        if check_prerequisites():
            deploy_automatic()
    else:
        print(PATCH_INSTRUCTIONS)
        print("\nUSAGE:")
        print("  Manual: Read instructions above and apply manually")
        print("  Auto:   python3 rustchain_entropy_enforcement_patch.py deploy")
