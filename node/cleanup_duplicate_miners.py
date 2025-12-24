#!/usr/bin/env python3
"""
RustChain Duplicate Miner Cleanup Script
Removes test miners and duplicate wallets on same hardware
"""

import sqlite3
import sys
from datetime import datetime

DB_PATH = "/root/rustchain/rustchain_v2.db"

# Legitimate miners to KEEP
LEGITIMATE_MINERS = [
    "ppc_g4_98ad7c5973eb4a3173090b9e66011a6b7b8c42cf9RTC",  # G4 (known wallet)
    "886c11d07cf87bc5cd4f930365af35c1254ea5RTC",            # Mac Pro
    "1c41ac9829dec18c2319333eabc09f529babf1RTC",            # Modern x86 #1
    "b0993965c3211d1a4acc4997d0fd286edccc52RTC",            # Modern x86 #2
]

# All enrolled miners that should be REMOVED
MINERS_TO_DELETE = [
    # Duplicate G4
    "ppc_g4_9b01f0c4cfe98ff5be0463947caec87339a0c5RTC",

    # Test wallets on MAC 3a53e0e44ed4
    "8a0743c9ca3534b0b1e9b4dff5d0972fbba795RTC",
    "e955ac5a49e75710d10fad245978362a437164RTC",
    "794f97cd0c6e0a1d6635c5d9d5e25c86e3fe84RTC",
    "e562e2877f7cde133e69da6fc561d18e3eda6aRTC",

    # Duplicate modern x86
    "a1b5960c523df67fd973649d899b42cc72c399RTC",
    "cdf53c4a21a35f136e32eada88f0f3854e74e0RTC",

    # Any test miners
    "g4-powerbook-01",
    "modern-x86-126",
]

def main():
    print("=" * 80)
    print("RustChain Duplicate Miner Cleanup")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Show current state
    print("📊 Current Network State:")
    cursor.execute("SELECT COUNT(DISTINCT miner_pk) FROM epoch_enroll")
    total = cursor.fetchone()[0]
    print(f"   Total enrolled miners: {total}")
    print()

    print("✅ Legitimate miners to KEEP:")
    for miner in LEGITIMATE_MINERS:
        cursor.execute("""
            SELECT ee.weight, COUNT(DISTINCT mm.mac_hash) as macs
            FROM epoch_enroll ee
            LEFT JOIN miner_macs mm ON ee.miner_pk = mm.miner
            WHERE ee.miner_pk = ?
            GROUP BY ee.weight
        """, (miner,))
        result = cursor.fetchone()
        if result:
            weight, macs = result
            print(f"   - {miner[:40]}... (weight: {weight}x, MACs: {macs})")
        else:
            print(f"   - {miner[:40]}... (NOT FOUND IN DB)")
    print()

    print("🗑️  Miners to DELETE:")
    deleted_count = 0
    for miner in MINERS_TO_DELETE:
        cursor.execute("SELECT weight FROM epoch_enroll WHERE miner_pk = ?", (miner,))
        result = cursor.fetchone()
        if result:
            print(f"   - {miner[:40]}... (weight: {result[0]}x)")
            deleted_count += 1
        else:
            print(f"   - {miner[:40]}... (already removed)")
    print()

    # Perform cleanup
    print("🔨 Performing cleanup...")
    print()

    for miner in MINERS_TO_DELETE:
        # Delete from epoch_enroll
        cursor.execute("DELETE FROM epoch_enroll WHERE miner_pk = ?", (miner,))

        # Delete from miner_macs
        cursor.execute("DELETE FROM miner_macs WHERE miner = ?", (miner,))

        # Delete from miner_attest_recent
        cursor.execute("DELETE FROM miner_attest_recent WHERE miner = ?", (miner,))

        if cursor.rowcount > 0:
            print(f"   ✅ Deleted: {miner[:40]}...")

    conn.commit()
    print()

    # Show final state
    print("📊 Final Network State:")
    cursor.execute("SELECT COUNT(DISTINCT miner_pk) FROM epoch_enroll")
    final_total = cursor.fetchone()[0]
    print(f"   Total enrolled miners: {final_total}")
    print()

    print("✅ Remaining miners:")
    cursor.execute("""
        SELECT ee.miner_pk, ee.weight, COUNT(DISTINCT mm.mac_hash) as mac_count
        FROM epoch_enroll ee
        LEFT JOIN miner_macs mm ON ee.miner_pk = mm.miner
        WHERE mm.last_ts > (strftime('%s', 'now') - 604800)
        GROUP BY ee.miner_pk
        ORDER BY ee.weight DESC
    """)
    for row in cursor.fetchall():
        miner, weight, mac_count = row
        print(f"   - {miner[:40]}... (weight: {weight}x, MACs: {mac_count})")
    print()

    cursor.execute("SELECT COUNT(DISTINCT miner_pk) FROM epoch_enroll")
    final_count = cursor.fetchone()[0]

    if final_count == 4:
        print("✅ SUCCESS: Network now has exactly 4 legitimate miners!")
    else:
        print(f"⚠️  WARNING: Expected 4 miners, got {final_count}")

    print()
    print("=" * 80)
    print("Cleanup complete!")
    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    main()
