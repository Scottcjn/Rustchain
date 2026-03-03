import importlib.util
import sqlite3
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

integrated_node = sys.modules["integrated_node"]


def _load_fleet_module():
    module_name = "fleet_immune_system_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips"
        / "python"
        / "rustchain"
        / "fleet_immune_system.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


fleet_mod = _load_fleet_module()


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


@pytest.fixture
def attest_client(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_attestation"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_attestation_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False, raising=False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False, raising=False)
    monkeypatch.setattr(integrated_node, "_check_hardware_binding", lambda *args, **kwargs: (True, "ok", ""))
    monkeypatch.setattr(integrated_node, "auto_induct_to_hall", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "record_macs", lambda *args, **kwargs: None)
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


def _minimal_valid_fingerprint(cv: float) -> dict:
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {
                    "cv": round(cv, 4),
                    "samples": 64,
                },
            },
        },
        "all_passed": True,
    }


def _shared_fleet_fingerprint() -> dict:
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {
                    "cv": 0.052,
                    "samples": 64,
                },
            },
            "cache_timing": {
                "passed": True,
                "data": {"l1_hit_ns": 4.1, "l2_hit_ns": 10.2},
            },
            "thermal_drift": {
                "passed": True,
                "data": {"entropy": 0.61},
            },
            "simd_identity": {
                "passed": True,
                "data": {"profile": "same-simd-profile"},
            },
        },
        "all_passed": True,
    }


def test_client_ip_from_request_trusts_spoofed_x_forwarded_for(attest_client):
    client, db_path = attest_client
    payload = {
        "miner": "spoof-demo-1",
        "device": {
            "device_family": "x86",
            "device_arch": "default",
            "arch": "default",
            "cores": 8,
            "cpu": "Intel Xeon",
            "serial_number": "SERIAL-001",
        },
        "signals": {
            "hostname": "shared-box-a",
            "macs": ["AA:BB:CC:DD:EE:01"],
        },
        "report": {
            "nonce": "nonce-001",
            "commitment": "commitment-001",
        },
        "fingerprint": _minimal_valid_fingerprint(0.05),
    }

    response = client.post(
        "/attest/submit",
        json=payload,
        headers={"X-Forwarded-For": "198.51.100.77"},
        environ_base={"REMOTE_ADDR": "10.0.0.9"},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["fingerprint_passed"] is True

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT source_ip FROM miner_attest_recent WHERE miner = ?",
            (payload["miner"],),
        ).fetchone()

    assert row == ("198.51.100.77",)


def test_same_subnet_and_shared_fingerprint_get_flagged():
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)

    for index in range(5):
        fleet_mod.record_fleet_signals_from_request(
            db,
            miner=f"baseline-miner-{index}",
            epoch=101,
            ip_address="10.0.0.25",
            attest_ts=1_000 + index * 5,
            fingerprint=_shared_fleet_fingerprint(),
        )

    scores = fleet_mod.compute_fleet_scores(db, 101)

    assert len(scores) == 5
    assert all(score > 0.7 for score in scores.values())


def test_spoofed_forwarded_ips_sparse_fingerprints_and_jitter_keep_scores_clean():
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)
    miners = [f"bypass-miner-{index}" for index in range(5)]

    for epoch in (201, 202, 203):
        for index, miner in enumerate(miners):
            fleet_mod.record_fleet_signals_from_request(
                db,
                miner=miner,
                epoch=epoch,
                ip_address=f"198.{10 + index}.{epoch % 255}.25",
                attest_ts=10_000 * epoch + index * 45,
                fingerprint=_minimal_valid_fingerprint(0.05 + index * 0.01),
            )

        scores = fleet_mod.compute_fleet_scores(db, epoch)

        assert set(scores) == set(miners)
        assert all(score < 0.3 for score in scores.values())
        assert all(score == 0.0 for score in scores.values())
        assert all(
            fleet_mod.apply_fleet_decay(2.5, score) == 2.5
            for score in scores.values()
        )
