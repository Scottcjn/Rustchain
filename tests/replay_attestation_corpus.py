#!/usr/bin/env python3
"""
Replay a saved attestation corpus entry against the Flask test client.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = PROJECT_ROOT / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"
TMP_ROOT = PROJECT_ROOT / "tests" / ".tmp_attestation"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "node"))

os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
os.environ.setdefault("DB_PATH", ":memory:")

from tests import mock_crypto

sys.modules["rustchain_crypto"] = mock_crypto


def _load_integrated_node():
    if "integrated_node" in sys.modules:
        return sys.modules["integrated_node"]

    spec = importlib.util.spec_from_file_location("integrated_node", NODE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["integrated_node"] = module
    spec.loader.exec_module(module)
    return module


def _init_attestation_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE blocked_wallets (
            wallet TEXT PRIMARY KEY,
            reason TEXT
        );
        CREATE TABLE balances (
            miner_pk TEXT PRIMARY KEY,
            balance_rtc REAL DEFAULT 0
        );
        CREATE TABLE epoch_enroll (
            epoch INTEGER NOT NULL,
            miner_pk TEXT NOT NULL,
            weight REAL NOT NULL,
            PRIMARY KEY (epoch, miner_pk)
        );
        CREATE TABLE miner_header_keys (
            miner_id TEXT PRIMARY KEY,
            pubkey_hex TEXT
        );
        CREATE TABLE tickets (
            ticket_id TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            commitment TEXT
        );
        CREATE TABLE oui_deny (
            oui TEXT PRIMARY KEY,
            vendor TEXT,
            enforce INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


def _apply_test_overrides(module, db_path: Path):
    original = {
        "DB_PATH": getattr(module, "DB_PATH", None),
        "HW_BINDING_V2": getattr(module, "HW_BINDING_V2", None),
        "HW_PROOF_AVAILABLE": getattr(module, "HW_PROOF_AVAILABLE", None),
        "check_ip_rate_limit": module.check_ip_rate_limit,
        "_check_hardware_binding": module._check_hardware_binding,
        "record_attestation_success": module.record_attestation_success,
        "record_macs": module.record_macs,
        "current_slot": module.current_slot,
        "slot_to_epoch": module.slot_to_epoch,
    }

    module.DB_PATH = str(db_path)
    module.HW_BINDING_V2 = False
    module.HW_PROOF_AVAILABLE = False
    module.check_ip_rate_limit = lambda client_ip, miner_id: (True, "ok")
    module._check_hardware_binding = lambda *args, **kwargs: (True, "ok", "")
    module.record_attestation_success = lambda *args, **kwargs: None
    module.record_macs = lambda *args, **kwargs: None
    module.current_slot = lambda: 12345
    module.slot_to_epoch = lambda slot: 85
    module.app.config["TESTING"] = True
    return original


def _restore_test_overrides(module, original):
    for name, value in original.items():
        setattr(module, name, value)


def parse_args():
    parser = argparse.ArgumentParser(description="Replay a saved attestation corpus JSON file")
    parser.add_argument("corpus_file", type=Path, help="Path to a JSON corpus entry")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload_path = args.corpus_file
    if not payload_path.exists():
        raise SystemExit(f"Corpus file not found: {payload_path}")

    raw_json = payload_path.read_text(encoding="utf-8")
    module = _load_integrated_node()

    TMP_ROOT.mkdir(exist_ok=True)
    db_path = TMP_ROOT / f"replay_{uuid.uuid4().hex}.sqlite3"
    _init_attestation_db(db_path)
    original = _apply_test_overrides(module, db_path)
    try:
        with module.app.test_client() as client:
            response = client.post("/attest/submit", data=raw_json, content_type="application/json")
            print(
                json.dumps(
                    {
                        "corpus_file": str(payload_path),
                        "status_code": response.status_code,
                        "response_json": response.get_json(silent=True),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if response.status_code < 500 else 1
    finally:
        _restore_test_overrides(module, original)
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
