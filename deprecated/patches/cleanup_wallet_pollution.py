#!/usr/bin/env python3
"""
RustChain Wallet Pollution Cleanup
Removes test/failed enrollment wallets, keeps only legitimate miners + founders
"""
import sqlite3

DB_PATH = 'rustchain_v2.db'

# Legitimate miners (actual hardware enrolled)
LEGIT_MINERS = [
    'ppc_g4_98ad7c5973eb4a3173090b9e66011a6b7b8c42cf9RTC',  # PowerPC G4
    '886c11d07cf87bc5cd4f930365af35c1254ea5RTC',            # Mac Pro
    '1c41ac9829dec18c2319333eabc09f529babf1RTC',            # Modern x86 #1
    'b0993965c3211d1a4acc4997d0fd286edccc52RTC',            # Modern x86 #2
]

# Founder wallets (6% premine)
FOUNDERS = [
    '9946531c1a976a41b2f60d11cceafd4578fb7aa09RTC',  # Community (201,326 RTC)
    '9682cebc5802df2274b1b7b91a7f6c627e7469e7dRTC',  # Dev Fund (150,994 RTC)
    '9a6cbf4a545976a191c8b68f5d12b2ccc0a5066aeRTC',  # Team Bounty (75,497 RTC)
    '9181f47720ee1bb063869fb3f58730f3d0ef9c005RTC',  # Founders (75,497 RTC)
]

WHITELIST = set(LEGIT_MINERS + FOUNDERS)

def main():
    print("="*80)
    print("RustChain Wallet Pollution Cleanup")
    print("="*80)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current state
    cursor.execute("SELECT COUNT(*) FROM balances")
    total_before = cursor.fetchone()[0]

    cursor.execute("SELECT miner_pk, balance_rtc FROM balances")
    all_wallets = cursor.fetchall()

    print(f"\nBefore cleanup:")
    print(f"  Total wallets: {total_before}")
    print(f"  Whitelist size: {len(WHITELIST)} (4 founders + 4 miners)")

    # Identify pollution
    to_delete = []
    kept_wallets = []

    for miner_pk, balance in all_wallets:
        if miner_pk in WHITELIST:
            kept_wallets.append((miner_pk, balance))
        else:
            to_delete.append(miner_pk)

    print(f"\nWallets to keep: {len(kept_wallets)}")
    for miner_pk, balance in kept_wallets:
        print(f"  ✓ {miner_pk[:45]}... = {balance:,.2f} RTC")

    print(f"\nWallets to delete: {len(to_delete)}")

    # Delete pollution
    deleted_count = 0
    for miner_pk in to_delete:
        cursor.execute("DELETE FROM balances WHERE miner_pk = ?", (miner_pk,))
        deleted_count += 1
        if deleted_count <= 10:  # Show first 10
            print(f"  🗑️  {miner_pk[:45]}...")

    if deleted_count > 10:
        print(f"  ... and {deleted_count - 10} more")

    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM balances")
    total_after = cursor.fetchone()[0]

    print(f"\n{'='*80}")
    print("CLEANUP COMPLETE")
    print(f"{'='*80}")
    print(f"Before: {total_before} wallets")
    print(f"After:  {total_after} wallets")
    print(f"Deleted: {deleted_count} pollution wallets")
    print(f"\n✅ Database cleaned!")

    conn.close()

if __name__ == "__main__":
    main()
