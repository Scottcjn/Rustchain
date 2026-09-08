# SPDX-License-Identifier: MIT
"""
Regression (audit A2): the WELCOME_BONUS_RTC welcome bonus (paid out of
founder_community) must only go to miners whose hardware fingerprint PASSED,
and the payer must never drive founder_community negative.

Before the fix /attest/submit called _check_welcome_bonus(miner) unconditionally
after fingerprint_passed had already been set to False for VM / emulator /
missing-evidence attests, so every fresh miner id (15 per IP per hour) drained
0.5 RTC from the community fund with zero proof of hardware.
"""

import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

EPOCH = 85
SOURCE = "founder_community"


def _load_integrated_node(db_path: Path, tag: str):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))

    from tests import mock_crypto

    sys.modules["rustchain_crypto"] = mock_crypto
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)

    spec = importlib.util.spec_from_file_location(f"integrated_node_welcome_gate_{tag}", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    module.DB_PATH = str(db_path)
    module.app.config["TESTING"] = True
    module.UTXO_DUAL_WRITE = False
    module.HW_BINDING_V2 = False
    module.HW_PROOF_AVAILABLE = False
    module.HAVE_REPLAY_DEFENSE = False
    module.HAVE_FLEET_IMMUNE = False
    module.HAVE_WARTHOG = False
    module.check_ip_rate_limit = lambda client_ip, miner_id: (True, "ok")
    module._check_hardware_binding = lambda *args, **kwargs: (True, "ok", "")
    module._check_oui_gate = lambda macs: (True, {"ok": True})
    module.wallet_review_gate_response = lambda miner: None
    module.record_macs = lambda *args, **kwargs: None
    module.current_slot = lambda: 12345
    module.slot_to_epoch = lambda slot: EPOCH
    # NOTE: _check_welcome_bonus is deliberately NOT stubbed - it is the code under test.
    return module


def _prepare_db(node, db_path: Path, nonces, source_balance_i64: int):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        node.attest_ensure_tables(conn)
        for nonce in nonces:
            conn.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (nonce, now + 3600))
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT);
            CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
            CREATE TABLE IF NOT EXISTS epoch_enroll (
                epoch INTEGER NOT NULL, miner_pk TEXT NOT NULL, weight INTEGER NOT NULL,
                PRIMARY KEY(epoch, miner_pk)
            );
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL, epoch INTEGER, miner_id TEXT NOT NULL,
                delta_i64 INTEGER NOT NULL, reason TEXT
            );
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT, device_arch TEXT,
                entropy_score REAL DEFAULT 0.0, fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT, signing_pubkey TEXT, fingerprint_checks_json TEXT
            );
            CREATE TABLE IF NOT EXISTS miner_attest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT NOT NULL, ts_ok INTEGER NOT NULL,
                device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0, fingerprint_checks_json TEXT
            );
            """
        )
        conn.execute("INSERT OR IGNORE INTO epoch_state(epoch, settled) VALUES (?, 0)", (EPOCH,))
        conn.execute(
            "INSERT INTO balances(miner_id, miner_pk, amount_i64, balance_rtc) VALUES (?, ?, ?, ?)",
            (SOURCE, SOURCE, source_balance_i64, source_balance_i64 / 1_000_000),
        )
        conn.commit()


def _payload(miner, nonce, fingerprint_ok: bool):
    if fingerprint_ok:
        checks = {
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 64}},
            "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        }
    else:
        # Client honestly reports a hypervisor: server marks fingerprint_passed=False
        # but still records the attestation (zero weight).
        checks = {
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 64}},
            "anti_emulation": {"passed": False, "data": {"vm_indicators": ["cpuinfo:hypervisor"]}},
        }
    return {
        "miner": miner,
        "miner_id": miner,
        "nonce": nonce,
        "device": {"model": "Generic CPU", "arch": "x86_64", "family": "x86_64", "cores": 4},
        "signals": {"hostname": "baremetal-host"},
        "report": {"nonce": nonce, "commitment": "commitment"},
        "fingerprint": {"checks": checks},
    }


def _state(db_path, miner):
    with sqlite3.connect(db_path) as conn:
        source = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (SOURCE,)).fetchone()[0]
        row = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner,)).fetchone()
        miner_bal = row[0] if row else 0
        bonus_rows = conn.execute(
            "SELECT COUNT(*) FROM ledger WHERE miner_id=? AND delta_i64 > 0 AND reason LIKE 'welcome_bonus:%'",
            (miner,),
        ).fetchone()[0]
        fp = conn.execute("SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
    return source, miner_bal, bonus_rows, (fp[0] if fp else None)


def test_failed_fingerprint_miner_gets_no_welcome_bonus(tmp_path):
    db_path = tmp_path / "welcome_gate_fail.sqlite3"
    node = _load_integrated_node(db_path, "fail")
    bonus_i64 = int(node.WELCOME_BONUS_RTC * 1_000_000)
    start = 10 * bonus_i64
    miner = "vm-farm-miner"
    _prepare_db(node, db_path, ["nonce-vm-1"], start)

    with node.app.test_client() as client:
        resp = client.post("/attest/submit", json=_payload(miner, "nonce-vm-1", fingerprint_ok=False))
    assert resp.status_code == 200, resp.get_json()

    source, miner_bal, bonus_rows, fp = _state(db_path, miner)
    assert fp == 0, "precondition: attestation recorded with fingerprint_passed=0"
    assert bonus_rows == 0, "failed-fingerprint miner was paid a welcome bonus (audit A2)"
    assert miner_bal == 0
    assert source == start, "founder_community was debited for a failed-fingerprint miner"


def test_passing_miner_gets_exactly_one_welcome_bonus(tmp_path):
    db_path = tmp_path / "welcome_gate_pass.sqlite3"
    node = _load_integrated_node(db_path, "pass")
    bonus_i64 = int(node.WELCOME_BONUS_RTC * 1_000_000)
    start = 10 * bonus_i64
    miner = "honest-baremetal-miner"
    _prepare_db(node, db_path, ["nonce-ok-1", "nonce-ok-2"], start)

    with node.app.test_client() as client:
        resp = client.post("/attest/submit", json=_payload(miner, "nonce-ok-1", fingerprint_ok=True))
        assert resp.status_code == 200, resp.get_json()
        source, miner_bal, bonus_rows, fp = _state(db_path, miner)
        assert fp == 1
        assert bonus_rows == 1
        assert miner_bal == bonus_i64
        assert source == start - bonus_i64

        # Second attestation: no second bonus.
        resp = client.post("/attest/submit", json=_payload(miner, "nonce-ok-2", fingerprint_ok=True))
        assert resp.status_code == 200, resp.get_json()
    source, miner_bal, bonus_rows, _ = _state(db_path, miner)
    assert bonus_rows == 1
    assert miner_bal == bonus_i64
    assert source == start - bonus_i64


def test_welcome_bonus_never_overdraws_source_fund(tmp_path):
    db_path = tmp_path / "welcome_gate_broke.sqlite3"
    node = _load_integrated_node(db_path, "broke")
    bonus_i64 = int(node.WELCOME_BONUS_RTC * 1_000_000)
    start = bonus_i64 // 2  # fund cannot cover one bonus
    miner = "late-honest-miner"
    _prepare_db(node, db_path, ["nonce-late-1"], start)

    with node.app.test_client() as client:
        resp = client.post("/attest/submit", json=_payload(miner, "nonce-late-1", fingerprint_ok=True))
    assert resp.status_code == 200, resp.get_json()

    source, miner_bal, bonus_rows, fp = _state(db_path, miner)
    assert fp == 1
    assert bonus_rows == 0
    assert miner_bal == 0
    assert source == start, "founder_community went below its balance (would have gone negative)"
    assert source >= 0
