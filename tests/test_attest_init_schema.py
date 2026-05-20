# SPDX-License-Identifier: MIT

import sqlite3
import sys
import uuid

integrated_node = sys.modules["integrated_node"]


def test_init_db_creates_attestation_submit_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh-rustchain.db"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "HAVE_REPLAY_DEFENSE", False)
    monkeypatch.setattr(integrated_node, "HAVE_WARTHOG", False)
    monkeypatch.setattr(integrated_node, "HAVE_BRIDGE", False)
    monkeypatch.setattr(integrated_node, "HAVE_UTXO", False)
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False)
    monkeypatch.setattr(integrated_node, "auto_induct_to_hall", lambda *args, **kwargs: None)

    integrated_node.init_db()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "blocked_wallets" in tables
    assert "ip_rate_limit" in tables
    assert "miner_attest_recent" in tables
    assert "miner_macs" in tables
    assert "hardware_bindings" in tables
    assert "oui_deny" in tables


def test_fresh_db_attestation_submit_does_not_crash_on_missing_schema(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "fresh-attest-route.db"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "HAVE_REPLAY_DEFENSE", False)
    monkeypatch.setattr(integrated_node, "HAVE_WARTHOG", False)
    monkeypatch.setattr(integrated_node, "HAVE_BRIDGE", False)
    monkeypatch.setattr(integrated_node, "HAVE_UTXO", False)
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False)
    monkeypatch.setattr(integrated_node, "auto_induct_to_hall", lambda *args, **kwargs: None)

    integrated_node.init_db()
    client = integrated_node.app.test_client()
    challenge = client.post("/attest/challenge", json={})
    assert challenge.status_code == 200

    miner = f"schema-fresh-{uuid.uuid4().hex[:8]}"
    payload = {
        "miner": miner,
        "device": {
            "device_family": "PowerPC",
            "device_arch": "g4",
            "cores": 1,
            "cpu": "PowerPC G4",
            "machine": "ppc",
        },
        "signals": {
            "hostname": "schema-fresh-host",
            "macs": ["AA:BB:CC:DD:EE:12"],
        },
        "report": {
            "nonce": challenge.get_json()["nonce"],
            "commitment": "schema-fresh-commitment",
        },
        "fingerprint": {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {
                        "vm_indicators": [],
                        "paths_checked": ["/proc/cpuinfo"],
                    },
                }
            },
            "all_passed": True,
        },
    }

    response = client.post("/attest/submit", json=payload)
    assert response.status_code != 500
    assert response.get_json()["ok"] is True

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT miner, fingerprint_passed FROM miner_attest_recent WHERE miner = ?",
            (miner,),
        ).fetchone()

    assert row == (miner, 0)
