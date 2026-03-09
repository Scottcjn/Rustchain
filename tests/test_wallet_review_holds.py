import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

integrated_node = sys.modules["integrated_node"]


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
        CREATE TABLE hardware_bindings (
            hardware_id TEXT PRIMARY KEY,
            bound_miner TEXT NOT NULL,
            device_arch TEXT,
            device_model TEXT,
            bound_at INTEGER,
            attestation_count INTEGER DEFAULT 0
        );
        CREATE TABLE miner_attest_recent (
            miner TEXT PRIMARY KEY,
            ts_ok INTEGER NOT NULL,
            device_family TEXT,
            device_arch TEXT,
            entropy_score REAL DEFAULT 0.0,
            fingerprint_passed INTEGER DEFAULT 0,
            source_ip TEXT
        );
        CREATE TABLE ip_rate_limit (
            client_ip TEXT NOT NULL,
            miner_id TEXT NOT NULL,
            ts INTEGER NOT NULL,
            PRIMARY KEY (client_ip, miner_id)
        );
        """
    )
    conn.commit()
    conn.close()


def _base_payload(miner: str = "review-miner") -> dict:
    return {
        "miner": miner,
        "device": {
            "device_family": "PowerPC",
            "device_arch": "power8",
            "cores": 8,
            "cpu": "IBM POWER8",
            "serial_number": f"SERIAL-{miner}",
        },
        "signals": {
            "hostname": "power8-host",
            "macs": ["AA:BB:CC:DD:EE:10"],
        },
        "report": {
            "nonce": f"nonce-{miner}",
            "commitment": f"commitment-{miner}",
        },
        "fingerprint": {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"]},
                },
            },
            "all_passed": True,
        },
    }


@pytest.fixture
def client(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_attestation"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_attestation_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False, raising=False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False, raising=False)
    monkeypatch.setattr(integrated_node, "_check_hardware_binding", lambda *args, **kwargs: (True, "ok", ""))
    monkeypatch.setattr(integrated_node, "check_ip_rate_limit", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(integrated_node, "record_macs", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "record_attestation_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "auto_induct_to_hall", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: 85)

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client, db_path

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def test_wallet_review_hold_returns_coaching_response(client):
    test_client, db_path = client
    with sqlite3.connect(db_path) as conn:
        integrated_node.ensure_wallet_review_tables(conn)
        conn.execute(
            """
            INSERT INTO wallet_review_holds(wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at)
            VALUES (?, 'needs_review', ?, ?, '', 1000, 0)
            """,
            ("review-miner", "fingerprint drift needs review", "Re-run attestation from the intended machine and wait for maintainer release."),
        )
        conn.commit()

    response = test_client.post("/attest/submit", json=_base_payload())

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "wallet_under_review"
    assert body["status"] == "needs_review"
    assert "wait for maintainer release" in body["coach_note"]


def test_wallet_review_release_restores_attestation_flow(client):
    test_client, db_path = client

    response = test_client.post(
        "/admin/wallet-review-holds",
        json={"wallet": "review-miner", "reason": "manual review", "coach_note": "fix and retry"},
        headers={"X-Admin-Key": "0" * 32},
    )
    assert response.status_code == 200
    hold_id = response.get_json()["id"]

    response = test_client.post(
        f"/admin/wallet-review-holds/{hold_id}/resolve",
        json={"action": "release", "reviewer_note": "release after verification"},
        headers={"X-Admin-Key": "0" * 32},
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "released"

    response = test_client.post("/attest/submit", json=_base_payload())
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_wallet_review_escalation_hard_blocks_attestation(client):
    test_client, db_path = client
    with sqlite3.connect(db_path) as conn:
        integrated_node.ensure_wallet_review_tables(conn)
        conn.execute(
            """
            INSERT INTO wallet_review_holds(wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at)
            VALUES (?, 'escalated', ?, '', '', 1000, 1001)
            """,
            ("review-miner", "replay abuse escalation"),
        )
        conn.commit()

    response = test_client.post("/attest/submit", json=_base_payload())

    assert response.status_code == 403
    body = response.get_json()
    assert body["error"] == "wallet_blocked"
    assert body["status"] == "escalated"
