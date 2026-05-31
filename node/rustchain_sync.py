#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import sqlite3
import hashlib
import json
import time
import logging
from copy import deepcopy
from typing import List, Dict, Any, Optional, Protocol


class StateProvider(Protocol):
    """Swappable source of syncable RustChain state."""

    def get_available_sync_tables(self) -> List[str]:
        ...

    def calculate_table_hash(self, table_name: str) -> str:
        ...

    def get_merkle_root(self) -> str:
        ...

    def get_primary_key(self, table_name: str) -> Optional[str]:
        ...

    def get_table_data(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> List[Dict[str, Any]]:
        ...

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        ...

    def get_count(self, table_name: str) -> int:
        ...


class SQLiteStateProvider:
    """
    SQLite-backed sync state provider.

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

    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger("RustChainSync")
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def _get_connection(self):
        """Open and return a new SQLite connection to the node database.

        Configures ``conn.row_factory = sqlite3.Row`` so that query results
        can be accessed by column name as well as by index.  Callers are
        responsible for closing the returned connection when finished.
        """
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

        pk = schema["pk"]
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY {pk} ASC")
            rows = cursor.fetchall()

            hasher = hashlib.sha256()
            for row in rows:
                row_dict = dict(row)
                row_str = json.dumps(row_dict, sort_keys=True, separators=(",", ":"))
                hasher.update(row_str.encode())

            return hasher.hexdigest()
        finally:
            conn.close()

    def get_merkle_root(self) -> str:
        """Generates a master Merkle root hash for all synced tables."""
        table_hashes = [self.calculate_table_hash(t) for t in self.SYNC_TABLES]
        combined = "".join(table_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_primary_key(self, table_name: str) -> Optional[str]:
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

                # SECURITY: Balances must NEVER be updated via peer sync.
                # Balance state is authoritative: it can only change through
                # local transaction processing (mining rewards, signed
                # transfers, epoch settlements).  Accepting balance data from
                # peers — even "increases only" — lets a single compromised
                # node inflate any wallet to an arbitrary value.
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
                            remote_val = int(sanitized[candidate_balance_col])
                            local_val = int(local_row[0])
                            if remote_val != local_val:
                                self.logger.warning(
                                    f"Rejected sync: Balance modification for "
                                    f"{sanitized[pk]} (local={local_val}, "
                                    f"remote={remote_val})"
                                )
                                continue

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

    def get_count(self, table_name: str) -> int:
        if table_name not in self.SYNC_TABLES:
            return 0
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            return int(count)
        finally:
            conn.close()


class InMemoryStateProvider:
    """Small in-memory provider for tests and embedded callers."""

    def __init__(
        self,
        tables: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        primary_keys: Optional[Dict[str, str]] = None,
    ):
        self.tables = deepcopy(tables or {})
        self.primary_keys = dict(primary_keys or {})

    def get_available_sync_tables(self) -> List[str]:
        return [name for name in self.tables if self.primary_keys.get(name)]

    def calculate_table_hash(self, table_name: str) -> str:
        if table_name not in self.get_available_sync_tables():
            return ""

        pk = self.primary_keys[table_name]
        rows = sorted(self.tables.get(table_name, []), key=lambda row: row.get(pk))
        hasher = hashlib.sha256()
        for row in rows:
            row_str = json.dumps(row, sort_keys=True, separators=(",", ":"))
            hasher.update(row_str.encode())
        return hasher.hexdigest()

    def get_merkle_root(self) -> str:
        combined = "".join(
            self.calculate_table_hash(table)
            for table in self.get_available_sync_tables()
        )
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_primary_key(self, table_name: str) -> Optional[str]:
        return self.primary_keys.get(table_name)

    def get_table_data(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> List[Dict[str, Any]]:
        if table_name not in self.get_available_sync_tables():
            return []
        rows = self.tables.get(table_name, [])
        return deepcopy(rows[int(offset): int(offset) + int(limit)])

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        pk = self.primary_keys.get(table_name)
        if not pk or table_name not in self.tables:
            return False

        rows_by_pk = {row.get(pk): dict(row) for row in self.tables[table_name]}
        for row in remote_data:
            if not isinstance(row, dict) or pk not in row:
                continue
            existing = rows_by_pk.get(row[pk], {})
            existing.update(row)
            rows_by_pk[row[pk]] = existing
        self.tables[table_name] = list(rows_by_pk.values())
        return True

    def get_count(self, table_name: str) -> int:
        if table_name not in self.get_available_sync_tables():
            return 0
        return len(self.tables.get(table_name, []))


class FallbackStateProvider:
    """Try multiple providers in order so callers can swap state sources safely."""

    def __init__(self, providers: List[StateProvider]):
        if not providers:
            raise ValueError("at least one state provider is required")
        self.providers = providers

    def _first_table_provider(self, table_name: str) -> Optional[StateProvider]:
        for provider in self.providers:
            try:
                if table_name in provider.get_available_sync_tables():
                    return provider
            except Exception:
                continue
        return None

    def _table_providers(self, table_name: str) -> List[StateProvider]:
        providers: List[StateProvider] = []
        for provider in self.providers:
            try:
                if table_name in provider.get_available_sync_tables():
                    providers.append(provider)
            except Exception:
                continue
        return providers

    def get_available_sync_tables(self) -> List[str]:
        tables: List[str] = []
        for provider in self.providers:
            try:
                for table in provider.get_available_sync_tables():
                    if table not in tables:
                        tables.append(table)
            except Exception:
                continue
        return tables

    def calculate_table_hash(self, table_name: str) -> str:
        for provider in self._table_providers(table_name):
            try:
                return provider.calculate_table_hash(table_name)
            except Exception:
                continue
        return ""

    def get_merkle_root(self) -> str:
        combined = "".join(
            self.calculate_table_hash(table)
            for table in self.get_available_sync_tables()
        )
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_primary_key(self, table_name: str) -> Optional[str]:
        for provider in self._table_providers(table_name):
            try:
                primary_key = provider.get_primary_key(table_name)
            except Exception:
                continue
            if primary_key:
                return primary_key
        return None

    def get_table_data(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> List[Dict[str, Any]]:
        for provider in self._table_providers(table_name):
            try:
                return provider.get_table_data(table_name, limit, offset)
            except Exception:
                continue
        return []

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        for provider in self._table_providers(table_name):
            try:
                if provider.apply_sync_payload(table_name, remote_data):
                    return True
            except Exception:
                continue
        return False

    def get_count(self, table_name: str) -> int:
        for provider in self._table_providers(table_name):
            try:
                return provider.get_count(table_name)
            except Exception:
                continue
        return 0


class RustChainSyncManager:
    """Handles bidirectional synchronization through a swappable state provider."""

    def __init__(
        self,
        db_path: str,
        admin_key: str,
        state_provider: Optional[StateProvider] = None,
    ):
        self.db_path = db_path
        self.admin_key = admin_key
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("RustChainSync")
        self.state_provider = state_provider or SQLiteStateProvider(
            db_path,
            logger=self.logger,
        )
        # Backward-compatible access for older tests that clear the SQLite schema cache.
        self._schema_cache = getattr(self.state_provider, "_schema_cache", {})

    @property
    def SYNC_TABLES(self) -> List[str]:
        return self.get_available_sync_tables()

    def get_available_sync_tables(self) -> List[str]:
        return self.state_provider.get_available_sync_tables()

    def calculate_table_hash(self, table_name: str) -> str:
        return self.state_provider.calculate_table_hash(table_name)

    def get_merkle_root(self) -> str:
        return self.state_provider.get_merkle_root()

    def _get_primary_key(self, table_name: str) -> Optional[str]:
        return self.state_provider.get_primary_key(table_name)

    def get_table_data(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> List[Dict[str, Any]]:
        return self.state_provider.get_table_data(table_name, limit, offset)

    def apply_sync_payload(self, table_name: str, remote_data: List[Dict[str, Any]]):
        return self.state_provider.apply_sync_payload(table_name, remote_data)

    def _get_count(self, table_name: str) -> int:
        return self.state_provider.get_count(table_name)

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
