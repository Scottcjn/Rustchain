# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_integrated_node(db_path: Path):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))

    from tests import mock_crypto

    sys.modules["rustchain_crypto"] = mock_crypto
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)

    spec = importlib.util.spec_from_file_location(
        "integrated_node_missing_fingerprint_reward_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    module.DB_PATH = str(db_path)
    module.app.config["TESTING"] = True
    module.UTXO_DUAL_WRITE = False
    module.HW_BINDING_V2 = False
    module.HW_PROOF_AVAILABLE = False
    module.HAVE_REPLAY_DEFENSE = False
    module.HAVE_WARTHOG = False
    module.check_ip_rate_limit = lambda client_ip, miner_id: (True, "ok")
    module._check_hardware_binding = lambda *args, **kwargs: (True, "ok", "")
    module._check_oui_gate = lambda macs: (True, {"ok": True})
    module.wallet_review_gate_response = lambda miner: None
    module.record_macs = lambda *args, **kwargs: None
    module._check_welcome_bonus = lambda miner: None
    module.current_slot = lambda: 12345
    module.slot_to_epoch = lambda slot: 85
    return module


def _prepare_attestation_db(node, db_path: Path, miner: str, epoch: int, nonce: str):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        node.attest_ensure_tables(conn)
        conn.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (nonce, now + 3600))
        conn.executescript(
            """
            CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT);
            CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
            CREATE TABLE epoch_enroll (
                epoch INTEGER NOT NULL,
                miner_pk TEXT NOT NULL,
                weight INTEGER NOT NULL,
                PRIMARY KEY(epoch, miner_pk)
            );
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                miner_pk TEXT,
                amount_i64 INTEGER DEFAULT 0,
                balance_rtc REAL DEFAULT 0
            );
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                signing_pubkey TEXT,
                fingerprint_checks_json TEXT
            );
            CREATE TABLE miner_attest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                fingerprint_checks_json TEXT
            );
            """
        )
        conn.execute("INSERT INTO epoch_state(epoch, settled) VALUES (?, 0)", (epoch,))
        conn.execute(
            "INSERT INTO balances(miner_id, miner_pk, amount_i64, balance_rtc) VALUES (?, ?, 0, 0)",
            (miner, miner),
        )
        conn.commit()


def test_missing_fingerprint_attestation_rejected_before_nonce_consumption(tmp_path):
    db_path = tmp_path / "missing_fingerprint_reward.sqlite3"
    node = _load_integrated_node(db_path)

    miner = "failed-fp-miner"
    epoch = 85
    nonce = "nonce-failed-fp"
    _prepare_attestation_db(node, db_path, miner, epoch, nonce)

    payload = {
        "miner": miner,
        "miner_id": miner,
        "nonce": nonce,
        "device": {"model": "Generic CPU", "arch": "x86_64", "family": "x86_64", "cores": 4},
        "signals": {"hostname": "baremetal-host"},
        "report": {"nonce": nonce, "commitment": "commitment"},
    }

    with node.app.test_client() as client:
        response = client.post("/attest/submit", json=payload)

    assert response.status_code == 422
    assert response.get_json()["code"] == "MISSING_FINGERPRINT"

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM nonces WHERE nonce=?", (nonce,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM used_nonces WHERE nonce=?", (nonce,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()[0] == 0
