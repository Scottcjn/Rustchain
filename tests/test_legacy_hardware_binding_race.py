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


def test_legacy_hardware_binding_ignores_spoofable_cpu_serial(tmp_path, monkeypatch):
    """Changing client-reported cpu_serial must not create a new legacy binding."""
    db_path = tmp_path / "hardware-binding-cpu-serial.sqlite3"
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

    base_device = {"device_model": "same-machine", "device_arch": "x86_64", "cores": 8}
    signals = {"macs": ["aa:bb:cc:dd:ee:ff"]}

    first_ok, _, first_bound = integrated_node._check_hardware_binding(
        "miner-a",
        {**base_device, "cpu_serial": "SERIAL-A"},
        signals,
        source_ip="203.0.113.50",
    )
    second_ok, _, second_bound = integrated_node._check_hardware_binding(
        "miner-b",
        {**base_device, "cpu_serial": "SERIAL-B"},
        signals,
        source_ip="203.0.113.50",
    )

    assert first_ok is True
    assert first_bound == "miner-a"
    assert second_ok is False
    assert second_bound == "miner-a"


def test_legacy_hardware_binding_migrates_same_wallet_old_hash(tmp_path, monkeypatch):
    """A same-wallet row keyed by the old client-serial hash is rewritten once."""
    db_path = tmp_path / "hardware-binding-legacy-migration.sqlite3"
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

    device = {
        "device_model": "shared-host",
        "device_arch": "x86_64",
        "device_family": "modern",
        "cores": 8,
        "cpu_serial": "OLD-CLIENT-SERIAL",
    }
    signals = {"macs": ["aa:bb:cc:dd:ee:ff"]}
    source_ip = "203.0.113.50"
    old_hardware_id = integrated_node._compute_legacy_hardware_id_with_client_serial(
        device, signals, source_ip=source_ip
    )
    new_hardware_id = integrated_node._compute_hardware_id(
        device, signals, source_ip=source_ip
    )
    assert old_hardware_id != new_hardware_id

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO hardware_bindings
                (hardware_id, bound_miner, device_arch, device_model, bound_at, attestation_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (old_hardware_id, "miner-a", "x86_64", "shared-host", 1_700_000_000, 4),
        )

    ok, reason, bound_miner = integrated_node._check_hardware_binding(
        "miner-a", device, signals, source_ip=source_ip
    )

    assert ok is True
    assert reason == "Authorized"
    assert bound_miner == "miner-a"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT hardware_id, bound_miner, attestation_count FROM hardware_bindings"
        ).fetchall()

    assert rows == [(new_hardware_id, "miner-a", 5)]


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
