#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import sqlite3
import hashlib
import json
import time
import logging
from typing import List, Dict, Any, Optional


class RustChainSyncManager:
    """
    Handles bidirectional SQLite synchronization between RustChain nodes.

    Security model:
    - Table names are allowlisted
    - Columns are schema-allowlisted per table (never trust remote payload keys)
    - Upserts use ON CONFLICT(pk) DO UPDATE to avoid REPLACE data loss semantics
    """

    BASE_SYNC_TABLES = [
        "miner_attest_recent",
        "balances",
        "epoch_rewards",
    ]

    OPTIONAL_SYNC_TABLES = [
        "transaction_history",
    ]

    def __init__(self, db_path: str, admin_key: str):
        self.db_path = db_path
        self.admin_key = admin_key
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("RustChainSync")
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _load_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]

        conn = self._get_connection()
        try:
            if not self._table_exists(conn, table_name):
                return None

            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            if not rows:
                return None

            columns = [r[1] for r in rows]
            pk_rows = [r for r in rows if int(r[5]) > 0]  # r[5] = pk order
            pk_rows = sorted(pk_rows, key=lambda r: int(r[5]))

            # We only support single-PK upsert path for now.
            pk_column = pk_rows[0][1] if pk_rows else None

            schema = {
                "columns": columns,
                "pk": pk_column,
            }
            self._schema_cache[table_name] = schema
            return schema
        finally:
            conn.close()

    def get_available_sync_tables(self) -> List[str]:
        tables: List[str] = []
        for t in self.BASE_SYNC_TABLES + self.OPTIONAL_SYNC_TABLES:
            schema = self._load_table_schema(t)
            if schema and schema.get("pk"):
                tables.append(t)
        return tables

    @property
    def SYNC_TABLES(self) -> List[str]:
        return self.get_available_sync_tables()

    def calculate_table_hash(self, table_name: str) -> str:
        """Calculates a deterministic hash of all rows in a table."""
        if table_name not in self.SYNC_TABLES:
            return ""

        schema = self._load_table_schema(table_name)
        if not schema:
            return ""

        conn = self._get_connection()
        cursor = conn.cursor()

        pk = schema["pk"]
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY {pk} ASC")
        rows = cursor.fetchall()

        hasher = hashlib.sha256()
        for row in rows:
            row_dict = dict(row)
            row_str = json.dumps(row_dict, sort_keys=True, separators=(",", ":"))
            hasher.update(row_str.encode())

        conn.close()
        return hasher.hexdigest()

    def get_merkle_root(self) -> str:
        """Generates a master Merkle root hash for all synced tables."""
        table_hashes = [self.calculate_table_hash(t) for t in self.SYNC_TABLES]
        combined = "".join(table_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_primary_key(self, table_name: str) -> Optional[str]:
        schema = self._load_table_schema(table_name)
        if not schema:
            return None
        return schema.get("pk")

    def get_table_data(self, table_name: str, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """Returns bounded data from a specific table as a list of dicts."""
        if table_name not in self.SYNC_TABLES:
            return []

        schema = self._load_table_schema(table_name)
        if not schema:
            return []

        pk = schema["pk"]
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {table_name} ORDER BY {pk} ASC LIMIT ? OFFSET ?",
            (int(limit), int(offset)),
        )
        data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return data

    def _balance_value_for_row(self, row: Dict[str, Any]) -> Optional[int]:
        for candidate in ("amount_i64", "balance_i64", "balance_urtc", "amount_rtc"):
            if candidate in row and row[candidate] is not None:
                try:
                    return int(row[candidate])
                except Exception:
                    return None
        return None

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        """Merges remote data into local database with conflict resolution and schema hardening."""
        if table_name not in self.SYNC_TABLES:
            return False

        schema = self._load_table_schema(table_name)
        if not schema:
            return False

        allowed_columns = set(schema["columns"])
        pk = schema["pk"]
        if not pk:
            self.logger.error(f"No PK found for {table_name}, skipping sync")
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            for row in remote_data:
                if not isinstance(row, dict):
                    continue

                if pk not in row:
                    continue

                sanitized = {k: v for k, v in row.items() if k in allowed_columns}
                if pk not in sanitized:
                    continue

                # Conflict resolution: Latest timestamp wins for attestations
                if table_name == "miner_attest_recent":
                    if "last_attest" in sanitized:
                        cursor.execute(f"SELECT last_attest FROM {table_name} WHERE {pk} = ?", (sanitized[pk],))
                        local_row = cursor.fetchone()
                        if local_row and local_row["last_attest"] is not None and local_row["last_attest"] >= sanitized["last_attest"]:
                            continue

                # For balances, reject if remote would reduce known local balance
                if table_name == "balances":
                    candidate_balance_col = None
                    for c in ("amount_i64", "balance_i64", "balance_urtc", "amount_rtc"):
                        if c in allowed_columns:
                            candidate_balance_col = c
                            break

                    if candidate_balance_col and candidate_balance_col in sanitized:
                        cursor.execute(
                            f"SELECT {candidate_balance_col} FROM {table_name} WHERE {pk} = ?",
                            (sanitized[pk],),
                        )
                        local_row = cursor.fetchone()
                        if local_row and local_row[0] is not None:
                            try:
                                if int(local_row[0]) > int(sanitized[candidate_balance_col]):
                                    self.logger.warning(f"Rejected sync: Balance reduction for {sanitized[pk]}")
                                    continue
                            except Exception:
                                pass

                # Safe upsert (avoid INSERT OR REPLACE data loss semantics)
                columns = list(sanitized.keys())
                placeholders = ", ".join(["?"] * len(columns))
                update_cols = [c for c in columns if c != pk]

                if not update_cols:
                    # PK-only row: ignore
                    continue

                update_expr = ", ".join([f"{c}=excluded.{c}" for c in update_cols])
                sql = (
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders}) "
                    f"ON CONFLICT({pk}) DO UPDATE SET {update_expr}"
                )
                cursor.execute(sql, [sanitized[c] for c in columns])

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
        tables = self.SYNC_TABLES
        status = {
            "timestamp": time.time(),
            "merkle_root": self.get_merkle_root(),
            "sync_tables": tables,
            "tables": {},
        }
        for t in tables:
            status["tables"][t] = {
                "hash": self.calculate_table_hash(t),
                "count": self._get_count(t),
                "pk": self._get_primary_key(t),
            }
        return status

    def _get_count(self, table_name: str) -> int:
        if table_name not in self.SYNC_TABLES:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        conn.close()
        return int(count)
