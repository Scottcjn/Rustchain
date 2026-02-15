import sqlite3
import time
import logging
import asyncio
from typing import Optional, List

class BridgeStorage:
    """
    SQLite Adapter for Rustchain v2 (Ported from SQLx/Postgres)
    Enhanced with asyncio.Lock for concurrency and deterministic IDs.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # Bridge Request Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bridge_requests (
                    id TEXT PRIMARY KEY,
                    user_address TEXT,
                    target_address TEXT,
                    amount INTEGER,
                    status TEXT,
                    tx_hash TEXT,
                    ergo_tx_id TEXT,
                    retry_count INTEGER,
                    updated_at INTEGER
                )
            """)
            # Re-org Resilience Table (Auditor)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS block_audits (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT,
                    verified_at INTEGER
                )
            """)
            conn.commit()

    async def record_block_hash(self, height: int, block_hash: str):
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("INSERT OR REPLACE INTO block_audits (height, block_hash, verified_at) VALUES (?, ?, ?)",
                               (height, block_hash, int(time.time())))
                    conn.commit()
            await asyncio.to_thread(_sync)

    async def get_block_hash(self, height: int) -> Optional[str]:
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT block_hash FROM block_audits WHERE height = ?", (height,))
                    row = cur.fetchone()
                    return row[0] if row else None
            return await asyncio.to_thread(_sync)

    async def get_pending_requests(self) -> List[dict]:
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM bridge_requests WHERE status = 'Pending'")
                    return [dict(row) for row in cur.fetchall()]
            return await asyncio.to_thread(_sync)

    async def get_broadcasting_requests(self) -> List[dict]:
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM bridge_requests WHERE status = 'Broadcasting'")
                    return [dict(row) for row in cur.fetchall()]
            return await asyncio.to_thread(_sync)

    async def update_request_status(self, request_id: str, status: str, ergo_tx_id: Optional[str] = None):
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    if ergo_tx_id:
                        cur.execute(
                            "UPDATE bridge_requests SET status = ?, ergo_tx_id = ?, updated_at = ? WHERE id = ?",
                            (status, ergo_tx_id, int(time.time()), request_id)
                        )
                    else:
                        cur.execute(
                            "UPDATE bridge_requests SET status = ?, updated_at = ? WHERE id = ?",
                            (status, int(time.time()), request_id)
                        )
                    conn.commit()
            await asyncio.to_thread(_sync)

    async def add_bridge_request(self, id: str, user: str, target: str, amount: int):
        async with self.lock:
            def _sync():
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR IGNORE INTO bridge_requests (id, user_address, target_address, amount, status, retry_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (id, user, target, amount, 'Pending', 0, int(time.time()))
                    )
                    conn.commit()
            await asyncio.to_thread(_sync)
