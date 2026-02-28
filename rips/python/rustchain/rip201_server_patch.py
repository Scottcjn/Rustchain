#!/usr/bin/env python3
"""
RIP-201 Server Integration Patch
=================================

This script patches rustchain_v2_integrated_v2.2.1_rip200.py to integrate
the fleet immune system. Run on VPS after copying fleet_immune_system.py.

Usage:
    python3 rip201_server_patch.py [--dry-run] [--server-file PATH]

Patches applied:
    1. Import fleet_immune_system module
    2. Update record_attestation_success() to collect fleet signals
    3. Hook calculate_immune_weights() into epoch settlement
    4. Register fleet admin endpoints
"""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime


def patch_file(filepath: str, dry_run: bool = False) -> bool:
    """Apply all patches to the server file."""

    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    original = content
    patches_applied = 0

    # ─── Patch 1: Add fleet immune system import ───
    marker = "from hashlib import blake2b"
    if marker in content and "fleet_immune_system" not in content:
        content = content.replace(
            marker,
            marker + """

# RIP-201: Fleet Detection Immune System
try:
    from fleet_immune_system import (
        record_fleet_signals, calculate_immune_weights,
        register_fleet_endpoints, ensure_schema as ensure_fleet_schema,
        get_fleet_report
    )
    HAVE_FLEET_IMMUNE = True
    print("[RIP-201] Fleet immune system loaded")
except Exception as _e:
    print(f"[RIP-201] Fleet immune system not available: {_e}")
    HAVE_FLEET_IMMUNE = False"""
        )
        patches_applied += 1
        print("  [1/4] Added fleet immune system imports")
    elif "fleet_immune_system" in content:
        print("  [1/4] Fleet imports already present — skipping")
    else:
        print(f"  [1/4] WARNING: Could not find import marker '{marker}'")

    # ─── Patch 2: Update record_attestation_success to pass signals & collect fleet data ───
    old_func = "def record_attestation_success(miner: str, device: dict, fingerprint_passed: bool = False):"
    new_func = "def record_attestation_success(miner: str, device: dict, fingerprint_passed: bool = False, signals: dict = None, fingerprint: dict = None, ip_address: str = None):"

    if old_func in content:
        content = content.replace(old_func, new_func)
        patches_applied += 1
        print("  [2/4] Updated record_attestation_success() signature")
    elif "signals: dict = None" in content and "record_attestation_success" in content:
        print("  [2/4] Function signature already updated — skipping")
    else:
        print("  [2/4] WARNING: Could not find record_attestation_success signature")

    # Add fleet signal hook after the INSERT in record_attestation_success
    attest_commit = """        conn.commit()"""
    fleet_hook = """        conn.commit()

        # RIP-201: Record fleet immune system signals
        if HAVE_FLEET_IMMUNE:
            try:
                record_fleet_signals(conn, miner, device, signals or {},
                                     fingerprint, now, ip_address=ip_address)
            except Exception as _fe:
                print(f"[RIP-201] Fleet signal recording warning: {_fe}")"""

    # Only patch the first occurrence in record_attestation_success context
    # Find the function, then find its conn.commit()
    func_match = re.search(r'def record_attestation_success\(.*?\n(.*?)(def |\Z)', content, re.DOTALL)
    if func_match and "RIP-201: Record fleet" not in content:
        func_body = func_match.group(0)
        if "conn.commit()" in func_body:
            patched_body = func_body.replace("        conn.commit()", fleet_hook, 1)
            content = content.replace(func_body, patched_body)
            patches_applied += 1
            print("  [2b/4] Added fleet signal hook to record_attestation_success()")
    elif "RIP-201: Record fleet" in content:
        print("  [2b/4] Fleet signal hook already present — skipping")

    # ─── Patch 3: Update submit_attestation call to pass extra args ───
    old_call = "record_attestation_success(miner, device, fingerprint_passed)"
    new_call = "record_attestation_success(miner, device, fingerprint_passed, signals=signals, fingerprint=fingerprint, ip_address=request.remote_addr)"

    if old_call in content:
        content = content.replace(old_call, new_call)
        patches_applied += 1
        print("  [3/4] Updated submit_attestation() call to pass signals/fingerprint/IP")
    elif "signals=signals" in content and "record_attestation_success" in content:
        print("  [3/4] Call already passes signals — skipping")
    else:
        print("  [3/4] WARNING: Could not find record_attestation_success call")

    # ─── Patch 4: Register fleet endpoints ───
    rewards_marker = '[REWARDS] Endpoints registered successfully'
    fleet_reg = """
    # RIP-201: Fleet immune system endpoints
    if HAVE_FLEET_IMMUNE:
        try:
            register_fleet_endpoints(app, DB_PATH)
            print("[RIP-201] Fleet immune endpoints registered")
        except Exception as e:
            print(f"[RIP-201] Failed to register fleet endpoints: {e}")"""

    if rewards_marker in content and "Fleet immune endpoints" not in content:
        # Insert after the rewards registration block
        insert_point = content.find(rewards_marker)
        # Find the end of the except block
        after_rewards = content[insert_point:]
        # Find the next blank line or next if/try block
        match = re.search(r'\n\n', after_rewards)
        if match:
            insert_pos = insert_point + match.end()
            content = content[:insert_pos] + fleet_reg + "\n" + content[insert_pos:]
            patches_applied += 1
            print("  [4/4] Registered fleet immune system endpoints")
        else:
            # Fallback: insert after the print line
            line_end = content.find('\n', insert_point)
            content = content[:line_end+1] + fleet_reg + "\n" + content[line_end+1:]
            patches_applied += 1
            print("  [4/4] Registered fleet immune system endpoints (fallback)")
    elif "Fleet immune endpoints" in content:
        print("  [4/4] Fleet endpoints already registered — skipping")
    else:
        print("  [4/4] WARNING: Could not find rewards registration marker")

    # ─── Apply ───
    if patches_applied == 0:
        print("\nNo patches needed — file already up to date.")
        return True

    if content == original:
        print("\nNo changes detected despite patches — check manually.")
        return False

    if dry_run:
        print(f"\n[DRY RUN] Would apply {patches_applied} patches to {filepath}")
        return True

    # Backup original
    backup_path = filepath + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"\nBackup saved: {backup_path}")

    # Write patched file
    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Applied {patches_applied} patches to {filepath}")
    return True


def main():
    parser = argparse.ArgumentParser(description="RIP-201 Fleet Immune System Server Patch")
    parser.add_argument("--dry-run", action="store_true", help="Preview patches without applying")
    parser.add_argument("--server-file", default=None,
                        help="Path to server file (default: auto-detect)")
    args = parser.parse_args()

    # Find server file
    candidates = [
        args.server_file,
        "/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py",
        os.path.expanduser("~/tmp_rustchain/node_package/rustchain_v2_integrated_v2.2.1_rip200.py"),
    ]

    server_file = None
    for c in candidates:
        if c and os.path.isfile(c):
            server_file = c
            break

    if not server_file:
        print("ERROR: Could not find server file. Use --server-file to specify path.")
        sys.exit(1)

    print(f"RIP-201 Fleet Immune System Patch")
    print(f"{'='*50}")
    print(f"Target: {server_file}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'='*50}\n")

    success = patch_file(server_file, dry_run=args.dry_run)

    if success:
        print("\nPatch complete. Restart the RustChain service:")
        print("  systemctl restart rustchain")
    else:
        print("\nPatch failed — check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
