#!/usr/bin/env python3
import sqlite3
import hashlib
import json
import time
import logging
from typing import List, Dict, Any, Optional

class RustChainSyncManager:
    """
    Handles bidirectional SQLite synchronization between RustChain nodes.
    Focuses on: miner_attest_recent, balances, epoch_rewards, and transaction_history.
    """
    
    SYNC_TABLES = [
        "miner_attest_recent",
        "balances",
        "epoch_rewards",
        "transaction_history"
    ]

    def __init__(self, db_path: str, admin_key: str):
        self.db_path = db_path
        self.admin_key = admin_key
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("RustChainSync")

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_table_hash(self, table_name: str) -> str:
        """Calculates a deterministic hash of all rows in a table."""
        if table_name not in self.SYNC_TABLES:
            return ""
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Sort by primary key or unique identifier for determinism
        pk = self._get_primary_key(table_name)
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY {pk} ASC")
        rows = cursor.fetchall()
        
        hasher = hashlib.sha256()
        for row in rows:
            # Convert row to deterministic JSON string
            row_dict = dict(row)
            row_str = json.dumps(row_dict, sort_keys=True)
            hasher.update(row_str.encode())
            
        conn.close()
        return hasher.hexdigest()

    def get_merkle_root(self) -> str:
        """Generates a master Merkle root hash for all synced tables."""
        table_hashes = [self.calculate_table_hash(t) for t in self.SYNC_TABLES]
        combined = "".join(table_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_primary_key(self, table_name: str) -> str:
        mapping = {
            "miner_attest_recent": "miner",
            "balances": "wallet",
            "epoch_rewards": "epoch",
            "transaction_history": "txid"
        }
        return mapping.get(table_name, "rowid")

    def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Returns all data from a specific table as a list of dicts."""
        if table_name not in self.SYNC_TABLES:
            return []
            
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return data

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        """Merges remote data into local database with conflict resolution."""
        if table_name not in self.SYNC_TABLES:
            return False
            
        conn = self._get_connection()
        cursor = conn.cursor()
        pk = self._get_primary_key(table_name)
        
        try:
            for row in remote_data:
                # Conflict resolution: Latest timestamp wins for attestations
                if table_name == "miner_attest_recent":
                    cursor.execute(f"SELECT last_attest FROM {table_name} WHERE {pk} = ?", (row[pk],))
                    local_row = cursor.fetchone()
                    if local_row and local_row["last_attest"] >= row["last_attest"]:
                        continue # Keep local
                
                # For balances, we reject if remote would reduce any balance (Security Req)
                if table_name == "balances":
                    cursor.execute(f"SELECT balance_urtc FROM {table_name} WHERE {pk} = ?", (row[pk],))
                    local_row = cursor.fetchone()
                    if local_row and local_row["balance_urtc"] > row["balance_urtc"]:
                        self.logger.warning(f"Rejected sync: Balance reduction for {row[pk]}")
                        continue
                
                # Upsert
                placeholders = ", ".join(["?"] * len(row))
                columns = ", ".join(row.keys())
                sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, list(row.values()))
                
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Sync error on {table_name}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_sync_status(self) -> Dict[str, Any]:
        """Returns metadata about the current state of synced tables."""
        status = {
            "timestamp": time.time(),
            "merkle_root": self.get_merkle_root(),
            "tables": {}
        }
        for t in self.SYNC_TABLES:
            status["tables"][t] = {
                "hash": self.calculate_table_hash(t),
                "count": self._get_count(t)
            }
        return status

    def _get_count(self, table_name: str) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        conn.close()
        return count
