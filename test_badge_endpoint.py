#!/usr/bin/env python3
"""
Test script for /api/badge/<wallet> endpoint
"""

import sqlite3
import json
import sys
import os

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'node'))

# Mock Flask app for testing
DB_PATH = "./rustchain_v2.db"

def slot_to_epoch(slot):
    """Convert slot number to epoch"""
    return int(slot) // 144  # EPOCH_SLOTS

def current_slot():
    """Get current slot number"""
    BLOCK_TIME = 600  # 10 minutes
    GENESIS_TIMESTAMP = 1764706927
    import time
    return (int(time.time()) - GENESIS_TIMESTAMP) // BLOCK_TIME

def get_mining_badge(wallet):
    """
    Test the badge endpoint logic
    """
    epoch = slot_to_epoch(current_slot())

    try:
        with sqlite3.connect(DB_PATH) as c:
            # Get balance - try both miner_pk and miner_id columns
            row = c.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_pk = ?", (wallet,)).fetchone()
            if not row or row[0] == 0:
                row = c.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_id = ?", (wallet,)).fetchone()
            balance_i64 = row[0] if row else 0
            balance_rtc = balance_i64 / 1000000.0

            # Check if miner is active
            active = False
            import time
            now = int(time.time())

            # Check enrollment in current epoch
            enroll_row = c.execute("SELECT COUNT(*) FROM epoch_enroll WHERE epoch = ? AND miner_pk = ?",
                                   (epoch, wallet)).fetchone()
            if enroll_row and enroll_row[0] > 0:
                active = True
            else:
                # Check recent attestation (within last hour)
                attest_row = c.execute(
                    "SELECT ts_ok FROM miner_attest_recent WHERE miner = ? AND ts_ok > ?",
                    (wallet, now - 3600)
                ).fetchone()
                if attest_row:
                    active = True
    except sqlite3.OperationalError as e:
        print(f"Database error (likely not initialized): {e}")
        # Return default values for testing
        balance_rtc = 0.0
        active = False

    # Determine message and color based on status
    if active:
        message = f"{balance_rtc:.1f} RTC | Epoch {epoch} | Active"
        color = "brightgreen"
    else:
        message = f"{balance_rtc:.1f} RTC | Epoch {epoch} | Inactive"
        color = "yellow"

    # Return shields.io-compatible JSON
    return json.dumps({
        "schemaVersion": 1,
        "label": "RustChain",
        "message": message,
        "color": color
    }, indent=2)

if __name__ == "__main__":
    print("Testing /api/badge/<wallet> endpoint logic")
    print("=" * 60)

    # Test with a sample wallet
    wallet = "test-wallet"
    result = get_mining_badge(wallet)

    print(f"Wallet: {wallet}")
    print(f"Result:")
    print(result)
    print()

    # Test the shields.io badge format
    badge_url = f"https://img.shields.io/endpoint?url=https://50.28.86.131/api/badge/{wallet}"
    print(f"Badge URL (for README):")
    print(badge_url)
    print()

    print("Example markdown for README:")
    print(f"![RustChain Mining]({badge_url})")
