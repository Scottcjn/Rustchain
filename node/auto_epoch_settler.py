#!/usr/bin/env python3
"""
RustChain Automatic Epoch Settlement Daemon
Runs in background and automatically settles completed epochs
"""
import time
import sqlite3
import requests
import sys
from datetime import datetime

# Configuration
NODE_URL = "http://localhost:8088"
DB_PATH = "/root/rustchain/rustchain_v2.db"
CHECK_INTERVAL = 300  # Check every 5 minutes
SLOTS_PER_EPOCH = 144

def get_current_slot():
    """Get current slot from node API"""
    try:
        resp = requests.get(f"{NODE_URL}/api/stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            epoch = data.get("epoch", 0)
            # Calculate approximate current slot
            return epoch * SLOTS_PER_EPOCH
    except Exception as e:
        print(f"Error getting current slot: {e}")
    return None

def get_current_epoch_from_db():
    """Get current epoch by checking max slot in headers table"""
    try:
        with sqlite3.connect(DB_PATH) as db:
            result = db.execute("SELECT MAX(slot) FROM headers").fetchone()
            if result and result[0]:
                max_slot = result[0]
                return max_slot // SLOTS_PER_EPOCH
    except Exception as e:
        print(f"Error querying database: {e}")
    return None

def get_unsettled_epochs():
    """Get list of epochs that should be settled but aren't"""
    try:
        with sqlite3.connect(DB_PATH) as db:
            # Get current epoch
            current_epoch = get_current_epoch_from_db()
            if current_epoch is None:
                # Fallback to API
                current_slot = get_current_slot()
                if current_slot:
                    current_epoch = current_slot // SLOTS_PER_EPOCH
                else:
                    return []

            # Find epochs that have headers but aren't settled
            # An epoch should be settled once the next epoch has started
            unsettled = []

            for epoch in range(max(0, current_epoch - 10), current_epoch):  # Check last 10 epochs
                # Check if epoch has any headers
                headers = db.execute(
                    "SELECT COUNT(*) FROM headers WHERE slot BETWEEN ? AND ?",
                    (epoch * SLOTS_PER_EPOCH, (epoch + 1) * SLOTS_PER_EPOCH - 1)
                ).fetchone()

                has_headers = headers and headers[0] > 0

                # Check if settled
                settled = db.execute(
                    "SELECT settled FROM epoch_state WHERE epoch=?",
                    (epoch,)
                ).fetchone()

                is_settled = settled and int(settled[0]) == 1

                if has_headers and not is_settled:
                    unsettled.append(epoch)

            return unsettled

    except Exception as e:
        print(f"Error finding unsettled epochs: {e}")
        return []

def settle_epoch_via_api(epoch):
    """Settle an epoch using the node API"""
    try:
        resp = requests.post(
            f"{NODE_URL}/rewards/settle",
            json={"epoch": epoch},
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                eligible = data.get("eligible", 0)
                distributed = data.get("distributed_rtc", 0)
                print(f"[OK] Settled epoch {epoch}: {eligible} miners, {distributed:.4f} RTC")
                return True
            else:
                error = data.get("error", "unknown")
                print(f"✗ Failed to settle epoch {epoch}: {error}")
        else:
            print(f"✗ HTTP error settling epoch {epoch}: {resp.status_code}")

    except Exception as e:
        print(f"✗ Exception settling epoch {epoch}: {e}")

    return False

def auto_settle_loop():
    """Main settlement loop"""
    print("="*70)
    print("RustChain Automatic Epoch Settler")
    print("="*70)
    print(f"Node: {NODE_URL}")
    print(f"Database: {DB_PATH}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking for unsettled epochs...")

            unsettled = get_unsettled_epochs()

            if unsettled:
                print(f"Found {len(unsettled)} unsettled epoch(s): {unsettled}")

                for epoch in sorted(unsettled):
                    print(f"\nSettling epoch {epoch}...")
                    settle_epoch_via_api(epoch)
                    time.sleep(2)  # Small delay between settlements

            else:
                print("No unsettled epochs found.")

            # Wait before next check
            print(f"Next check in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n⛔ Automatic settlement stopped")
            sys.exit(0)

        except Exception as e:
            print(f"Error in settlement loop: {e}")
            print(f"Retrying in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    auto_settle_loop()
