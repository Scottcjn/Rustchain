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
                attestation_count INTEGER DEFAULT 0,
                stable_hw_id TEXT
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
                attestation_count INTEGER DEFAULT 0,
                stable_hw_id TEXT
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
                attestation_count INTEGER DEFAULT 0,
                stable_hw_id TEXT
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


_SCHEMA = """
    CREATE TABLE hardware_bindings (
        hardware_id TEXT PRIMARY KEY,
        bound_miner TEXT NOT NULL,
        device_arch TEXT,
        device_model TEXT,
        bound_at INTEGER NOT NULL,
        attestation_count INTEGER DEFAULT 0,
        stable_hw_id TEXT
    )
"""


def test_legacy_migration_cannot_be_stolen_with_alternate_client_serial(tmp_path, monkeypatch):
    """#71: a different wallet must not seize the hardened key by changing the
    client-controlled serial so its legacy lookup misses the victim's row."""
    db_path = tmp_path / "hb-71-takeover.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))

    base = {"device_model": "shared-host", "device_arch": "x86_64",
            "device_family": "modern", "cores": 8}
    victim_device = {**base, "cpu_serial": "S_REAL"}
    attacker_device = {**base, "cpu_serial": "S_FAKE"}
    signals = {"macs": ["aa:bb:cc:dd:ee:ff"]}
    source_ip = "203.0.113.50"

    # Seed the victim's pre-#8267 binding keyed with THEIR real serial, and
    # stamp its serial-free stable identity the way a migrated/backfilled row has.
    victim_old = integrated_node._compute_legacy_hardware_id_with_client_serial(
        victim_device, signals, source_ip=source_ip)
    hardened = integrated_node._compute_hardware_id(
        victim_device, signals, source_ip=source_ip)
    assert victim_old != hardened
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO hardware_bindings (hardware_id, bound_miner, device_arch, "
            "device_model, bound_at, attestation_count, stable_hw_id) VALUES (?,?,?,?,?,?,?)",
            (victim_old, "victim-wallet", "x86_64", "shared-host", 1_700_000_000, 4, hardened),
        )

    # Attacker presents the same machine tuple but a DIFFERENT serial.
    a_ok, _, a_bound = integrated_node._check_hardware_binding(
        "attacker-wallet", attacker_device, signals, source_ip=source_ip)
    assert a_ok is False
    assert a_bound == "victim-wallet"

    # Victim continuity still works.
    v_ok, _, v_bound = integrated_node._check_hardware_binding(
        "victim-wallet", victim_device, signals, source_ip=source_ip)
    assert v_ok is True
    assert v_bound == "victim-wallet"


def test_arch_model_are_not_treated_as_machine_identity(tmp_path, monkeypatch):
    """Regression: two UNRELATED miners sharing a common arch/model but on
    different machines (IP/MACs) must both bind. arch/model is not an identity."""
    db_path = tmp_path / "hb-arch-model.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))

    common = {"device_model": "Threadripper", "device_arch": "x86_64",
              "device_family": "modern", "cores": 32, "cpu_serial": "X"}
    # Miner A on one machine.
    a_ok, _, _ = integrated_node._check_hardware_binding(
        "miner-a", common, {"macs": ["11:11:11:11:11:11"]}, source_ip="198.51.100.1")
    # Miner B: identical arch/model, DIFFERENT machine (different IP + MACs).
    b_ok, b_reason, _ = integrated_node._check_hardware_binding(
        "miner-b", common, {"macs": ["22:22:22:22:22:22"]}, source_ip="198.51.100.2")
    assert a_ok is True
    assert b_ok is True, f"honest second miner rejected: {b_reason}"


def test_binding_self_heals_when_stable_column_missing(tmp_path, monkeypatch):
    """gunicorn safety: init_db() runs only under __main__, so the attest path
    must add stable_hw_id itself. A bare pre-existing table (no column) must not
    cause a fail-closed attest outage."""
    db_path = tmp_path / "hb-no-column.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE hardware_bindings (hardware_id TEXT PRIMARY KEY, "
            "bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, "
            "bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)"
        )
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "_HWB_STABLE_COL_READY_FOR", None)
    dev = {"device_model": "m", "device_arch": "x86_64", "device_family": "modern",
           "cores": 4, "cpu_serial": "Z"}
    ok, reason, _ = integrated_node._check_hardware_binding(
        "miner-x", dev, {"macs": ["33:33:33:33:33:33"]}, source_ip="192.0.2.9")
    assert ok is True, f"attest failed closed on missing column: {reason}"
    with sqlite3.connect(db_path) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(hardware_bindings)").fetchall()]
    assert "stable_hw_id" in cols


def test_legacy_null_row_self_heals_then_resists_takeover(tmp_path, monkeypatch):
    """Honest deploy-state coverage for #71. A real pre-#8267 row arrives with
    stable_hw_id IS NULL (no backfill is possible: the serial-free identity needs
    IP/MACs/cores the old row never stored). Documented remediation: the moment
    the legitimate owner re-attests once (same serial, <=10min attest interval),
    its row is migrated + stamped, and an alternate-serial takeover then FAILS.
    """
    db_path = tmp_path / "hb-null-selfheal.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "_HWB_STABLE_COL_READY_FOR", None)

    base = {"device_model": "shared-host", "device_arch": "x86_64",
            "device_family": "modern", "cores": 8}
    victim = {**base, "cpu_serial": "S_REAL"}
    attacker = {**base, "cpu_serial": "S_FAKE"}
    signals = {"macs": ["aa:bb:cc:dd:ee:ff"]}
    ip = "203.0.113.50"

    victim_legacy = integrated_node._compute_legacy_hardware_id_with_client_serial(
        victim, signals, source_ip=ip)
    with sqlite3.connect(db_path) as conn:  # unmigrated row: stable_hw_id NULL
        conn.execute(
            "INSERT INTO hardware_bindings (hardware_id, bound_miner, device_arch, "
            "device_model, bound_at, attestation_count) VALUES (?,?,?,?,?,?)",
            (victim_legacy, "victim-wallet", "x86_64", "shared-host", 1_700_000_000, 4))

    # Owner re-attests once with their own serial -> migrate + stamp stable_hw_id.
    ok, _, bound = integrated_node._check_hardware_binding("victim-wallet", victim, signals, source_ip=ip)
    assert ok is True and bound == "victim-wallet"
    with sqlite3.connect(db_path) as conn:
        stamped = conn.execute(
            "SELECT stable_hw_id FROM hardware_bindings WHERE bound_miner='victim-wallet'").fetchone()[0]
    assert stamped is not None, "self-heal must stamp stable_hw_id on owner re-attest"

    # Now the alternate-serial takeover is blocked.
    a_ok, _, a_bound = integrated_node._check_hardware_binding("attacker-wallet", attacker, signals, source_ip=ip)
    assert a_ok is False
    assert a_bound == "victim-wallet"
