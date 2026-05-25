#!/usr/bin/env python3
"""
RustChain Automatic Epoch Settlement Daemon
Runs in background and automatically settles completed epochs
"""
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

import requests

# Configure logging (daemon-friendly — writes to stderr + syslog in systemd)
logger = logging.getLogger("rustchain.epoch_settler")

# Configuration — environment variables with defaults
NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "http://localhost:8088")
DB_PATH = os.environ.get("RUSTCHAIN_DB_PATH", "/root/rustchain/rustchain_v2.db")
CHECK_INTERVAL = int(os.environ.get("RUSTCHAIN_SETTLE_INTERVAL", "300"))
SLOTS_PER_EPOCH = int(os.environ.get("RUSTCHAIN_SLOTS_PER_EPOCH", "144"))


def get_current_slot():
    """Get current slot from node API"""
    try:
        resp = requests.get(f"{NODE_URL}/api/stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            epoch = data.get("epoch", 0)
            return epoch * SLOTS_PER_EPOCH
    except requests.RequestException as e:
        logger.warning("Error getting current slot: %s", e)
    except Exception as e:
        logger.error("Unexpected error getting current slot: %s", e)
    return None


def get_current_epoch_from_db():
    """Get current epoch by checking max slot in headers table"""
    try:
        with sqlite3.connect(DB_PATH) as db:
            result = db.execute("SELECT MAX(slot) FROM headers").fetchone()
            if result and result[0]:
                max_slot = result[0]
                return max_slot // SLOTS_PER_EPOCH
    except sqlite3.Error as e:
        logger.warning("Database error querying current epoch: %s", e)
    except Exception as e:
        logger.error("Unexpected error querying current epoch: %s", e)
    return None


def get_unsettled_epochs():
    """Get list of epochs that should be settled but aren't"""
    try:
        with sqlite3.connect(DB_PATH) as db:
            current_epoch = get_current_epoch_from_db()
            if current_epoch is None:
                current_slot = get_current_slot()
                if current_slot:
                    current_epoch = current_slot // SLOTS_PER_EPOCH
                else:
                    logger.warning("Cannot determine current epoch — no unsettled check possible")
                    return []

            unsettled = []
            for epoch in range(max(0, current_epoch - 10), current_epoch):
                headers = db.execute(
                    "SELECT COUNT(*) FROM headers WHERE slot BETWEEN ? AND ?",
                    (epoch * SLOTS_PER_EPOCH, (epoch + 1) * SLOTS_PER_EPOCH - 1)
                ).fetchone()
                has_headers = headers and headers[0] > 0

                settled = db.execute(
                    "SELECT settled FROM epoch_state WHERE epoch=?",
                    (epoch,)
                ).fetchone()
                is_settled = settled and int(settled[0]) == 1

                if has_headers and not is_settled:
                    unsettled.append(epoch)

            return unsettled

    except sqlite3.Error as e:
        logger.error("Database error finding unsettled epochs: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error finding unsettled epochs: %s", e)
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
                logger.info("Settled epoch %d: %d miners, %.4f RTC", epoch, eligible, distributed)
                return True
            else:
                error = data.get("error", "unknown")
                logger.warning("Failed to settle epoch %d: %s", epoch, error)
        else:
            logger.warning("HTTP error settling epoch %d: %s", epoch, resp.status_code)

    except requests.RequestException as e:
        logger.error("Network error settling epoch %d: %s", epoch, e)
    except Exception as e:
        logger.error("Unexpected error settling epoch %d: %s", epoch, e)

    return False


def auto_settle_loop():
    """Main settlement loop"""
    logger.info("=" * 70)
    logger.info("RustChain Automatic Epoch Settler")
    logger.info("=" * 70)
    logger.info("Node: %s", NODE_URL)
    logger.info("Database: %s", DB_PATH)
    logger.info("Check interval: %ds", CHECK_INTERVAL)
    logger.info("Epoch slots: %d", SLOTS_PER_EPOCH)
    logger.info("Started: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 70)

    while True:
        try:
            logger.info("Checking for unsettled epochs...")
            unsettled = get_unsettled_epochs()

            if unsettled:
                logger.info("Found %d unsettled epoch(s): %s", len(unsettled), unsettled)
                for epoch in sorted(unsettled):
                    logger.info("Settling epoch %d...", epoch)
                    settle_epoch_via_api(epoch)
                    time.sleep(2)
            else:
                logger.debug("No unsettled epochs found.")

            logger.debug("Next check in %ds...", CHECK_INTERVAL)
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Automatic settlement stopped")
            sys.exit(0)

        except Exception as e:
            logger.exception("Error in settlement loop")
            logger.info("Retrying in %ds...", CHECK_INTERVAL)
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    auto_settle_loop()
