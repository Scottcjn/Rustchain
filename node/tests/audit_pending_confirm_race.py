# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path


ADMIN_KEY = "a" * 32
SERVER_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"
_SERVER_MODULE = None
_IMPORT_DB_PATH = str(Path(tempfile.mkdtemp(prefix="rustchain-pending-import-")) / "import.db")


def load_server(db_path: str):
    global _SERVER_MODULE

    os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ["DB_PATH"] = db_path

    server_dir = str(SERVER_PATH.parent)
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)

    if _SERVER_MODULE is None:
        os.environ["RUSTCHAIN_DB_PATH"] = _IMPORT_DB_PATH
        os.environ["DB_PATH"] = _IMPORT_DB_PATH
        spec = importlib.util.spec_from_file_location("rustchain_pending_confirm_audit", SERVER_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _SERVER_MODULE = mod

    _SERVER_MODULE.DB_PATH = db_path
    _SERVER_MODULE.app.config["DB_PATH"] = db_path
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ["DB_PATH"] = db_path
    return _SERVER_MODULE


def seed_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0,
                balance_rtc REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                confirms_at INTEGER NOT NULL,
                tx_hash TEXT,
                voided_by TEXT,
                voided_reason TEXT,
                confirmed_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                epoch INTEGER,
                miner_id TEXT,
                delta_i64 INTEGER,
                reason TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
            ("alice", 1_000_000, 1.0),
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
            ("bob", 0, 0.0),
        )
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO pending_ledger
            (ts, epoch, from_miner, to_miner, amount_i64, reason, status, created_at, confirms_at, tx_hash)
            VALUES (?, 1, 'alice', 'bob', 400000, 'race-test', 'pending', ?, ?, 'racehash')
            """,
            (now, now, now - 1),
        )


class ReadySelectCursor:
    def __init__(self, cursor, barrier):
        self._cursor = cursor
        self._barrier = barrier
        self._ready_select = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self._ready_select = (
            normalized.startswith("SELECT id, from_miner, to_miner, amount_i64, reason, epoch, tx_hash")
            and "FROM pending_ledger" in normalized
            and "status = 'pending'" in normalized
        )
        self._cursor.execute(sql, params)
        return self

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._ready_select:
            try:
                self._barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                # After the fix, BEGIN IMMEDIATE serializes the second worker
                # before it reaches this SELECT. Continue so the first request
                # can commit and the second can observe no pending rows.
                pass
        return rows

    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class ReadySelectConnection:
    def __init__(self, conn, barrier):
        self._conn = conn
        self._barrier = barrier

    def cursor(self):
        return ReadySelectCursor(self._conn.cursor(), self._barrier)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def rollback(self):
        return self._conn.rollback()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_pending_confirm_concurrent_requests_do_not_double_apply(monkeypatch, tmp_path):
    db_path = str(tmp_path / "race.db")
    seed_db(db_path)
    mod = load_server(db_path)
    barrier = threading.Barrier(2)
    real_connect = sqlite3.connect

    def connect_with_barrier(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        if args and args[0] == db_path:
            return ReadySelectConnection(conn, barrier)
        return conn

    monkeypatch.setattr(mod.sqlite3, "connect", connect_with_barrier)

    responses = []

    def call_confirm():
        with mod.app.test_client() as client:
            resp = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY})
            responses.append((resp.status_code, resp.get_json()))

    t1 = threading.Thread(target=call_confirm)
    t2 = threading.Thread(target=call_confirm)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with real_connect(db_path) as conn:
        balances = dict(conn.execute("SELECT miner_id, amount_i64 FROM balances"))
        ledger_rows = conn.execute(
            "SELECT miner_id, delta_i64, reason FROM ledger ORDER BY id"
        ).fetchall()
        status = conn.execute(
            "SELECT status FROM pending_ledger WHERE tx_hash='racehash'"
        ).fetchone()[0]

    status_codes = [status_code for status_code, _ in responses]
    confirmed_counts = sorted(payload["confirmed_count"] for _, payload in responses)

    print("responses=", responses)
    print("balances=", balances)
    print("ledger_rows=", ledger_rows)
    print("status=", status)

    assert status_codes == [200, 200]
    assert confirmed_counts == [0, 1]
    assert status == "confirmed"
    assert balances["alice"] == 600_000
    assert balances["bob"] == 400_000
    assert len(ledger_rows) == 2


def test_pending_confirm_single_request_still_confirms_once(tmp_path):
    db_path = str(tmp_path / "single.db")
    seed_db(db_path)
    mod = load_server(db_path)

    with mod.app.test_client() as client:
        resp = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY})
        assert resp.status_code == 200
        assert resp.get_json()["confirmed_count"] == 1

    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute("SELECT miner_id, amount_i64 FROM balances"))
        ledger_count = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        status = conn.execute(
            "SELECT status FROM pending_ledger WHERE tx_hash='racehash'"
        ).fetchone()[0]

    assert status == "confirmed"
    assert balances["alice"] == 600_000
    assert balances["bob"] == 400_000
    assert ledger_count == 2
