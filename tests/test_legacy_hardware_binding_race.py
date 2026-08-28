# SPDX-License-Identifier: MIT
"""Regression coverage for the legacy one-hardware/one-wallet guard."""

import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor


integrated_node = sys.modules["integrated_node"]


class _BarrierCursor:
    """Make both workers observe the absent binding before either inserts."""

    def __init__(self, owner, cursor, select_barrier):
        self._owner = owner
        self._cursor = cursor
        self._select_barrier = select_barrier

    def execute(self, sql, parameters=()):
        normalized_sql = sql.strip().upper()
        if normalized_sql.startswith("BEGIN IMMEDIATE"):
            self._owner.uses_write_transaction = True

        result = self._cursor.execute(sql, parameters)
        if (
            not self._owner.uses_write_transaction
            and "SELECT bound_miner, attestation_count FROM hardware_bindings" in sql
        ):
            self._select_barrier.wait(timeout=5)
        return result

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _BarrierConnection:
    def __init__(self, connection, select_barrier):
        self._connection = connection
        self._select_barrier = select_barrier
        self.uses_write_transaction = False

    def cursor(self, *args, **kwargs):
        return _BarrierCursor(
            self, self._connection.cursor(*args, **kwargs), self._select_barrier
        )

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_legacy_hardware_binding_rechecks_after_concurrent_insert(tmp_path, monkeypatch):
    """A conflicting legacy bind must be rejected even when it loses an insert race."""
    db_path = tmp_path / "hardware-binding-race.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE hardware_bindings (
                hardware_id TEXT PRIMARY KEY,
                bound_miner TEXT NOT NULL,
                device_arch TEXT,
                device_model TEXT,
                bound_at INTEGER NOT NULL,
                attestation_count INTEGER DEFAULT 0
            )
            """
        )

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    real_connect = sqlite3.connect
    select_barrier = threading.Barrier(2)

    def gated_connect(*args, **kwargs):
        return _BarrierConnection(real_connect(*args, **kwargs), select_barrier)

    monkeypatch.setattr(integrated_node.sqlite3, "connect", gated_connect)

    device = {"device_model": "same-machine", "device_arch": "x86_64", "cores": 8}

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda miner: integrated_node._check_hardware_binding(
                    miner, device, {}, source_ip="203.0.113.50"
                ),
                ("miner-a", "miner-b"),
            )
        )

    accepted = [result for result in results if result[0]]
    assert len(accepted) == 1

    with real_connect(db_path) as conn:
        (bound_miner,) = conn.execute(
            "SELECT bound_miner FROM hardware_bindings"
        ).fetchone()

    rejected = next(result for result in results if not result[0])
    assert rejected[2] == bound_miner


def test_legacy_hardware_binding_fails_closed_when_db_unavailable(monkeypatch):
    """Binding state must not be treated as accepted when SQLite cannot be read."""

    def locked_connect(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(integrated_node, "DB_PATH", "unavailable.sqlite3")
    monkeypatch.setattr(integrated_node.sqlite3, "connect", locked_connect)

    ok, reason, bound_miner = integrated_node._check_hardware_binding(
        "miner-a",
        {"device_model": "same-machine", "device_arch": "x86_64", "cores": 8},
        {},
        source_ip="203.0.113.50",
    )

    assert ok is False
    assert reason == "hardware_binding_unavailable"
    assert bound_miner == ""
