# SPDX-License-Identifier: MIT
import importlib.util
import gc
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
MODULE_NAME = "rustchain_integrated_governance_propose_nonce_test"


def load_integrated_module(db_path: str, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-" + "0" * 32)
    monkeypatch.setenv("RUSTCHAIN_DB_PATH", db_path)
    monkeypatch.syspath_prepend(str(NODE_DIR))
    sys.modules.pop("payout_preflight", None)
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    module.DB_PATH = db_path
    module.app.config["DB_PATH"] = db_path
    module.app.config["TESTING"] = True
    return module


def test_governance_propose_rejects_replayed_nonce(monkeypatch):
    tempdir = tempfile.TemporaryDirectory()
    try:
        db_path = str(Path(tempdir.name) / "governance.db")
        mod = load_integrated_module(db_path, monkeypatch)
        try:
            monkeypatch.setattr(mod, "verify_rtc_signature", lambda *_args, **_kwargs: True)
            monkeypatch.setattr(mod, "address_from_pubkey", lambda _public_key: "RTCwallet")

            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                mod._ensure_governance_tables(cur)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
                )
                conn.execute("INSERT INTO balances VALUES ('RTCwallet', 11000000)")
                conn.commit()
            finally:
                conn.close()

            payload = {
                "wallet": "RTCwallet",
                "title": "Replay protected proposal",
                "description": "This signed proposal must only be accepted once.",
                "nonce": "proposal-nonce-1",
                "signature": "aa" * 64,
                "public_key": "bb" * 32,
            }

            with mod.app.test_client() as client:
                first = client.post("/governance/propose", json=payload)
                replay = client.post("/governance/propose", json=payload)

            assert first.status_code == 201
            assert replay.status_code == 409
            assert replay.get_json() == {
                "ok": False,
                "error": "nonce_already_used",
                "nonce": "proposal-nonce-1",
            }

            conn = sqlite3.connect(db_path)
            try:
                proposal_count = conn.execute("SELECT COUNT(*) FROM governance_proposals").fetchone()[0]
                nonce_count = conn.execute(
                    "SELECT COUNT(*) FROM governance_nonces WHERE wallet = ? AND nonce = ?",
                    ("RTCwallet", "proposal-nonce-1"),
                ).fetchone()[0]
            finally:
                conn.close()

            assert proposal_count == 1
            assert nonce_count == 1
        finally:
            sys.modules.pop(MODULE_NAME, None)
            mod = None
            gc.collect()
    finally:
        gc.collect()
        try:
            tempdir.cleanup()
        except OSError:
            pass
