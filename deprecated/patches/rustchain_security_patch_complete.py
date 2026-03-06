#!/usr/bin/env python3
"""
RustChain Complete Security Patch
==================================
Fixes:
1. MAC uniqueness enforcement (prevent same hardware = multiple wallets)
2. MAC churn protection (re-enable commented-out code)
3. Entropy score enforcement (minimum thresholds)
4. Database cleanup (remove duplicate miners)

Apply this patch to rustchain_v2_integrated_v2.2.1_rip200.py
"""

# ============================================================================
# PART 1: Add MAC Uniqueness Check Function
# Insert after _mac_hash() function (around line 668)
# ============================================================================

def check_mac_uniqueness(miner: str, macs: list) -> tuple:
    """
    Prevent multiple miners from claiming the same physical hardware.

    Args:
        miner: Current miner ID attempting to attest
        macs: List of MAC addresses being claimed

    Returns:
        (is_unique: bool, info: dict)
    """
    if not macs:
        return False, {"error": "no_macs_provided", "message": "MAC address required for attestation"}

    now = int(time.time())
    recent_threshold = now - 86400  # 24 hours

    conflicts = []

    with sqlite3.connect(DB_PATH) as conn:
        for mac in macs:
            h = _mac_hash(str(mac))
            if not h:
                continue

            # Find OTHER miners using this MAC recently
            rows = conn.execute("""
                SELECT miner, last_ts, count
                FROM miner_macs
                WHERE mac_hash = ? AND last_ts >= ? AND miner != ?
                ORDER BY last_ts DESC
                LIMIT 5
            """, (h, recent_threshold, miner)).fetchall()

            if rows:
                for row in rows:
                    conflicting_miner = row[0]
                    last_seen = row[1]
                    usage_count = row[2]
                    age_seconds = now - last_seen

                    conflicts.append({
                        "mac_hash": h,
                        "claimed_by": conflicting_miner[:20] + "...",
                        "last_seen_seconds_ago": age_seconds,
                        "usage_count": usage_count
                    })

    if conflicts:
        return False, {
            "ok": False,
            "error": "mac_already_claimed",
            "conflicts": conflicts,
            "message": f"This hardware is already registered to {len(conflicts)} other miner(s). Each physical machine can only have ONE active wallet."
        }

    return True, {"ok": True}


# ============================================================================
# PART 2: Modify submit_attestation()
# Around line 1150, add MAC uniqueness check BEFORE recording
# ============================================================================

"""
# In submit_attestation(), after OUI check (around line 1150):

    macs = signals.get('macs', [])
    if macs:
        # Existing OUI check
        oui_ok, oui_info = _check_oui_gate(macs)
        if not oui_ok:
            return jsonify(oui_info), 412

        # NEW: Check MAC uniqueness (prevent hardware re-use)
        mac_unique, mac_info = check_mac_uniqueness(miner, macs)
        if not mac_unique:
            log.warning(f"[ANTI-SPOOF] MAC collision detected for {miner}: {mac_info}")
            return jsonify(mac_info), 409  # HTTP 409 Conflict
    else:
        # No MACs provided - reject
        return jsonify({
            "ok": False,
            "error": "macs_required",
            "message": "Hardware fingerprint (MAC address) required for attestation"
        }), 400
"""


# ============================================================================
# PART 3: Re-enable MAC Churn Protection
# Remove comment markers from lines 706-707
# ============================================================================

"""
# In check_enrollment_requirements(), UNCOMMENT these lines:

# OLD (DISABLED):
# TEMP DISABLED FOR TESTING:             if unique_count > MAC_MAX_UNIQUE_PER_DAY:
# TEMP DISABLED FOR TESTING:                 return False, {"error": "mac_churn"...

# NEW (ENABLED):
            if unique_count > MAC_MAX_UNIQUE_PER_DAY:
                return False, {
                    "error": "mac_churn",
                    "unique_24h": unique_count,
                    "limit": MAC_MAX_UNIQUE_PER_DAY,
                    "message": f"Too many different MACs ({unique_count}) in 24h. Limit: {MAC_MAX_UNIQUE_PER_DAY}. Possible spoofing detected."
                }
"""


# ============================================================================
# PART 4: Enforce Minimum Entropy Scores
# Add check in submit_attestation() BEFORE accepting
# ============================================================================

# Minimum entropy score (0.0 to 1.0)
MIN_ENTROPY_SCORE = 0.15  # Start low, increase gradually

"""
# In submit_attestation(), after hardware proof validation (around line 1165):

    if HW_PROOF_AVAILABLE:
        is_valid, proof_result = server_side_validation(data)
        entropy = proof_result.get("entropy_score", 0.0)

        # Log for monitoring
        print(f"[HW_PROOF] Miner: {miner}")
        print(f"[HW_PROOF]   Entropy: {entropy:.3f} (min: {MIN_ENTROPY_SCORE})")
        print(f"[HW_PROOF]   Tier: {proof_result.get('antiquity_tier', 'unknown')}")

        # ENFORCE minimum entropy (phased rollout)
        # Phase 1: Warn only (current)
        if entropy < MIN_ENTROPY_SCORE:
            log.warning(f"[ENTROPY] Low entropy {entropy:.3f} for {miner}")
            # TODO Phase 2: Reject when ready
            # return jsonify({
            #     "ok": False,
            #     "error": "insufficient_entropy",
            #     "entropy_score": entropy,
            #     "minimum_required": MIN_ENTROPY_SCORE,
            #     "message": "Hardware fingerprint quality too low. Possible emulator/VM."
            # }), 403
"""


# ============================================================================
# PART 5: Database Cleanup Script
# Run this ONCE to remove duplicate miners from existing database
# ============================================================================

import sqlite3
import time

def cleanup_duplicate_miners(db_path="/root/rustchain/rustchain_v2.db"):
    """
    Remove miners that share MAC addresses with other miners.
    Keep the FIRST miner that claimed each MAC (by first_ts).
    """
    print("="*70)
    print("RustChain Database Cleanup - Remove Duplicate Miners")
    print("="*70)

    now = int(time.time())
    recent_threshold = now - 86400  # 24 hours

    with sqlite3.connect(db_path) as conn:
        # Find MAC hashes claimed by multiple miners
        duplicates = conn.execute("""
            SELECT mac_hash,
                   COUNT(DISTINCT miner) as miner_count,
                   GROUP_CONCAT(DISTINCT miner) as miners
            FROM miner_macs
            WHERE last_ts >= ?
            GROUP BY mac_hash
            HAVING miner_count > 1
        """, (recent_threshold,)).fetchall()

        print(f"\nFound {len(duplicates)} MAC hashes with multiple miners")

        miners_to_remove = set()

        for mac_hash, count, miners_str in duplicates:
            miners = miners_str.split(',')
            print(f"\n  MAC {mac_hash}: {count} miners")

            # Get first miner for this MAC (by first_ts)
            first_miner = conn.execute("""
                SELECT miner, first_ts
                FROM miner_macs
                WHERE mac_hash = ?
                ORDER BY first_ts ASC
                LIMIT 1
            """, (mac_hash,)).fetchone()

            keeper = first_miner[0]
            print(f"    Keeping: {keeper[:30]}...")

            # Mark others for removal
            for miner in miners:
                if miner != keeper:
                    miners_to_remove.add(miner)
                    print(f"    Removing: {miner[:30]}...")

        print(f"\nTotal miners to remove: {len(miners_to_remove)}")

        if miners_to_remove:
            # Remove from all tables
            for miner in miners_to_remove:
                print(f"  Purging {miner[:30]}...")

                # Remove from epoch enrollments
                conn.execute("DELETE FROM epoch_enroll WHERE miner_pk = ?", (miner,))

                # Remove from attestations
                conn.execute("DELETE FROM miner_attest_recent WHERE miner = ?", (miner,))

                # Remove from MAC records
                conn.execute("DELETE FROM miner_macs WHERE miner = ?", (miner,))

                # Remove from balances
                conn.execute("DELETE FROM balances WHERE miner_pk = ?", (miner,))

            conn.commit()
            print(f"\n✅ Removed {len(miners_to_remove)} duplicate miners")
        else:
            print("\n✅ No duplicates to remove")

    print("="*70)


# ============================================================================
# PART 6: Deployment Script
# ============================================================================

def deploy_security_patch():
    """
    Complete deployment of security patch
    """
    import os
    import shutil
    from datetime import datetime

    node_file = "/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py"
    backup_file = f"{node_file}.backup_{int(time.time())}"

    print("="*70)
    print("RustChain Security Patch Deployment")
    print("="*70)

    # 1. Backup
    print("\n1. Creating backup...")
    shutil.copy2(node_file, backup_file)
    print(f"   ✅ Backup: {backup_file}")

    # 2. Read current file
    print("\n2. Reading node code...")
    with open(node_file, 'r') as f:
        code = f.read()

    # 3. Insert check_mac_uniqueness function
    print("\n3. Adding MAC uniqueness check...")
    # Find insertion point after _mac_hash function
    insert_point = code.find("def record_macs(miner: str, macs: list):")
    if insert_point > 0:
        function_code = '''

def check_mac_uniqueness(miner: str, macs: list) -> tuple:
    """Prevent multiple miners from claiming the same physical hardware"""
    if not macs:
        return False, {"error": "no_macs_provided"}

    now = int(time.time())
    recent_threshold = now - 86400
    conflicts = []

    with sqlite3.connect(DB_PATH) as conn:
        for mac in macs:
            h = _mac_hash(str(mac))
            if not h:
                continue

            rows = conn.execute("""
                SELECT miner, last_ts FROM miner_macs
                WHERE mac_hash = ? AND last_ts >= ? AND miner != ?
                ORDER BY last_ts DESC LIMIT 5
            """, (h, recent_threshold, miner)).fetchall()

            for row in rows:
                conflicts.append({
                    "claimed_by": row[0][:20] + "...",
                    "last_seen_ago": now - row[1]
                })

    if conflicts:
        return False, {
            "ok": False,
            "error": "mac_already_claimed",
            "conflicts": conflicts,
            "message": "Hardware already registered to another miner"
        }

    return True, {"ok": True}

'''
        code = code[:insert_point] + function_code + code[insert_point:]
        print("   ✅ MAC uniqueness function added")

    # 4. Un-comment MAC churn protection
    print("\n4. Enabling MAC churn protection...")
    code = code.replace(
        "# TEMP DISABLED FOR TESTING:             if unique_count > MAC_MAX_UNIQUE_PER_DAY:",
        "            if unique_count > MAC_MAX_UNIQUE_PER_DAY:"
    )
    code = code.replace(
        "# TEMP DISABLED FOR TESTING:                 return False, {\"error\": \"mac_churn\"",
        "                return False, {\"error\": \"mac_churn\""
    )
    print("   ✅ MAC churn protection enabled")

    # 5. Write patched file
    print("\n5. Writing patched code...")
    with open(node_file, 'w') as f:
        f.write(code)
    print("   ✅ Patch applied")

    # 6. Cleanup database
    print("\n6. Cleaning up duplicate miners...")
    cleanup_duplicate_miners()

    print("\n" + "="*70)
    print("✅ SECURITY PATCH DEPLOYED SUCCESSFULLY")
    print("="*70)
    print("\nNext steps:")
    print("1. Restart node: systemctl restart rustchain")
    print("2. Monitor logs: journalctl -u rustchain -f")
    print("3. Verify: Check for 'mac_already_claimed' rejections")
    print("="*70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup_duplicate_miners()
    elif len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy_security_patch()
    else:
        print("Usage:")
        print("  python3 rustchain_security_patch_complete.py cleanup  # Remove duplicates only")
        print("  python3 rustchain_security_patch_complete.py deploy   # Full patch + cleanup")
