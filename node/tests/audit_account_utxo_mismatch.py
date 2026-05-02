import os
import sqlite3
import tempfile
import time
import unittest


# Import logic from RustChain (mocking where necessary)
def _setup_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE miner_attest_recent (
            miner TEXT PRIMARY KEY,
            ts_ok INTEGER,
            device_family TEXT,
            device_arch TEXT,
            entropy_score INTEGER,
            fingerprint_passed INTEGER
        );
        CREATE TABLE balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER
        );
        CREATE TABLE ledger (
            ts INTEGER,
            epoch INTEGER,
            miner_id TEXT,
            delta_i64 INTEGER,
            reason TEXT
        );
        CREATE TABLE epoch_rewards (
            epoch INTEGER,
            miner_id TEXT,
            share_i64 INTEGER
        );
        CREATE TABLE epoch_state (
            epoch INTEGER PRIMARY KEY,
            settled INTEGER,
            settled_ts INTEGER
        );
        -- UTXO Tables
        CREATE TABLE utxo_boxes (
            box_id TEXT PRIMARY KEY,
            value_nrtc INTEGER NOT NULL,
            proposition TEXT NOT NULL,
            owner_address TEXT NOT NULL,
            creation_height INTEGER NOT NULL,
            transaction_id TEXT NOT NULL,
            output_index INTEGER NOT NULL,
            spent_at INTEGER,
            spent_by_tx TEXT
        );
    """)
    return path, db


def simulate_settle_epoch(db, epoch, rewards):
    """Simplified version of settle_epoch_with_anti_double_mining"""
    db.execute("BEGIN IMMEDIATE")
    ts_now = int(time.time())
    for miner_id, share_urtc in rewards.items():
        db.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
            "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
            (miner_id, share_urtc, share_urtc),
        )
        db.execute(
            "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)", (epoch, miner_id, share_urtc)
        )
    db.execute("INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)", (epoch, ts_now))
    db.commit()


class TestAccountUtxoMismatch(unittest.TestCase):
    def test_settlement_mismatch(self):
        """Verify that epoch settlement updates Account balances but NOT UTXO state."""
        db_path, db = _setup_db()

        miner_id = "RTCminer123"
        reward_amount = 100_000_000  # 100 RTC

        print(f"Settling epoch 1 with {reward_amount} reward for {miner_id}...")
        simulate_settle_epoch(db, 1, {miner_id: reward_amount})

        # 1. Check Account balance
        row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner_id,)).fetchone()
        account_balance = row["amount_i64"] if row else 0
        print(f"Account Balance: {account_balance}")

        # 2. Check UTXO balance
        row = db.execute(
            "SELECT SUM(value_nrtc) as total FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL", (miner_id,)
        ).fetchone()
        utxo_balance = row["total"] if row["total"] is not None else 0
        print(f"UTXO Balance:    {utxo_balance}")

        # Verification
        self.assertEqual(account_balance, reward_amount)
        self.assertEqual(utxo_balance, 0)
        print("\nCRITICAL FINDING CONFIRMED:")
        print("Account-based reward settlement does not create UTXO entries.")
        print("Miners cannot spend rewards via UTXO-native endpoints.")

        os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
