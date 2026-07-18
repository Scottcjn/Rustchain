# SPDX-License-Identifier: MIT
"""
Regression tests: miner_attest_recent.warthog_bonus must track the CURRENT
attestation, not ratchet up permanently.

The submit handler only writes the column when the freshly computed bonus is
> 1.0, and record_attestation_success() does not carry warthog_bonus in its
ON CONFLICT DO UPDATE list. So once a miner earns the dual-mining bonus, no
code path ever writes 1.0 back: the miner can stop dual-mining, or start
failing the hardware fingerprint (which the handler explicitly intends to deny
the bonus), and keep the multiplier on every future epoch.

rip_200_round_robin_1cpu1vote.calculate_epoch_rewards_time_aged reads
COALESCE(warthog_bonus, 1.0) straight into the miner's epoch reward weight, so
the stale value dilutes every honest miner's share of the fixed epoch pot.
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
NONCE = "nonce-warthog"
MINER = "warthog-miner"


def _load_integrated_node(db_path: Path, warthog_verified: bool):
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
        f"integrated_node_warthog_test_{warthog_verified}_{db_path.name}",
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
    module.HAVE_FLEET_IMMUNE = False
    module.HAVE_WARTHOG = True
    module.check_ip_rate_limit = lambda client_ip, miner_id: (True, "ok")
    module._check_hardware_binding = lambda *args, **kwargs: (True, "ok", "")
    module._check_oui_gate = lambda macs: (True, {"ok": True})
    module.wallet_review_gate_response = lambda miner: None
    module.record_macs = lambda *args, **kwargs: None
    module._check_welcome_bonus = lambda miner: None
    module.current_slot = lambda: 12345
    module.slot_to_epoch = lambda slot: EPOCH
    module.validate_fingerprint_data = lambda fingerprint, claimed_device=None: (True, "ok")
    module.verify_warthog_proof = lambda proof, miner: (warthog_verified, 1.15, "own_node")
    module.record_warthog_proof = lambda *args, **kwargs: None
    return module


def _prepare_db(node, db_path: Path, seeded_bonus: float):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        node.attest_ensure_tables(conn)
        conn.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (NONCE, now + 3600))
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT);
            CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                signing_pubkey TEXT,
                fingerprint_checks_json TEXT,
                warthog_bonus REAL DEFAULT 1.0
            );
            CREATE TABLE IF NOT EXISTS miner_attest_history (
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
        conn.execute("INSERT OR IGNORE INTO epoch_state(epoch, settled) VALUES (?, 0)", (EPOCH,))
        conn.execute(
            "INSERT OR IGNORE INTO balances(miner_id, miner_pk, amount_i64, balance_rtc)"
            " VALUES (?, ?, 0, 0)",
            (MINER, MINER),
        )
        # The miner previously verified a Warthog proof and earned the 1.15x tier.
        conn.execute(
            "INSERT INTO miner_attest_recent"
            " (miner, ts_ok, device_arch, fingerprint_passed, warthog_bonus)"
            " VALUES (?, ?, 'x86_64', 1, ?)",
            (MINER, now - 3600, seeded_bonus),
        )
        conn.commit()


def _payload(with_warthog: bool):
    payload = {
        "miner": MINER,
        "miner_id": MINER,
        "nonce": NONCE,
        "device": {"model": "Generic CPU", "arch": "x86_64", "family": "x86_64", "cores": 4},
        "signals": {"hostname": "baremetal-host"},
        "report": {"nonce": NONCE, "commitment": "commitment"},
        "fingerprint": {
            "checks": {
                "clock_drift": {"passed": True, "data": {"cv": 0.03}},
                "anti_emulation": {"passed": True, "data": {}},
            }
        },
    }
    if with_warthog:
        payload["warthog"] = {
            "enabled": True,
            "proof_type": "own_node",
            "node": {"synced": True, "height": 500000},
            "balance": "42.5",
            "collected_at": int(time.time()),
        }
    return payload


def _stored_bonus(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT warthog_bonus FROM miner_attest_recent WHERE miner = ?", (MINER,)
        ).fetchone()[0]


def test_attestation_without_warthog_proof_clears_stale_bonus(tmp_path):
    """Miner stops dual-mining: the bonus must not survive the next attestation."""
    db_path = tmp_path / "warthog_stop.sqlite3"
    node = _load_integrated_node(db_path, warthog_verified=True)
    _prepare_db(node, db_path, seeded_bonus=1.15)

    with node.app.test_client() as client:
        response = client.post("/attest/submit", json=_payload(with_warthog=False))

    assert response.status_code == 200, response.get_data(as_text=True)
    assert _stored_bonus(db_path) == 1.0, "bonus must reflect the current attestation"


def test_failed_warthog_verification_clears_stale_bonus(tmp_path):
    """Proof sent but rejected: the previously earned bonus must be revoked."""
    db_path = tmp_path / "warthog_fail.sqlite3"
    node = _load_integrated_node(db_path, warthog_verified=False)
    _prepare_db(node, db_path, seeded_bonus=1.15)

    with node.app.test_client() as client:
        response = client.post("/attest/submit", json=_payload(with_warthog=True))

    assert response.status_code == 200, response.get_data(as_text=True)
    assert _stored_bonus(db_path) == 1.0, "a rejected proof must not keep the bonus"


def test_verified_warthog_proof_still_records_bonus(tmp_path):
    """Guard against over-reach: a genuine proof must still earn the bonus."""
    db_path = tmp_path / "warthog_ok.sqlite3"
    node = _load_integrated_node(db_path, warthog_verified=True)
    _prepare_db(node, db_path, seeded_bonus=1.0)

    with node.app.test_client() as client:
        response = client.post("/attest/submit", json=_payload(with_warthog=True))

    assert response.status_code == 200, response.get_data(as_text=True)
    assert _stored_bonus(db_path) == 1.15, "verified dual-mining still earns 1.15x"
