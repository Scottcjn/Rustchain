import sqlite3
import threading
import unittest
import os
import time
from rip302_agent_economy import _adjust_balance, init_agent_economy_tables

class TestAgentEconomyRace(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_economy_race.db"
        init_agent_economy_tables(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
            conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)", ("RACE_MINER", 1000))
            conn.commit()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.db_path + "-shm"):
            os.remove(self.db_path + "-shm")
        if os.path.exists(self.db_path + "-wal"):
            os.remove(self.db_path + "-wal")

    def worker(self, delta, results):
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                _adjust_balance(conn.cursor(), "RACE_MINER", delta)
                results.append(True)
        except Exception as e:
            print(f"Worker failed: {e}")
            results.append(False)

    def test_concurrent_balance_updates(self):
        results = []
        threads = []
        # 50 threads adding 10, 50 threads subtracting 10
        for i in range(50):
            threads.append(threading.Thread(target=self.worker, args=(10, results)))
            threads.append(threading.Thread(target=self.worker, args=(-10, results)))

        for t in threads: t.start()
        for t in threads: t.join()

        # Check 1: Did all workers succeed?
        self.assertEqual(len([r for r in results if r]), 100, f"Some workers failed! Success rate: {len([r for r in results if r])}/100")

        # Check 2: Is the final balance correct?
        with sqlite3.connect(self.db_path) as conn:
            final_balance = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", ("RACE_MINER",)).fetchone()[0]
        
        self.assertEqual(final_balance, 1000, f"Race condition detected! Final balance: {final_balance}")

if __name__ == "__main__":
    unittest.main()
