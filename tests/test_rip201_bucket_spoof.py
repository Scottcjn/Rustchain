import importlib.util
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

integrated_node = sys.modules["integrated_node"]


def _load_fleet_module():
    module_name = "fleet_immune_system_bucket_test"
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
    monkeypatch.setattr(integrated_node, "check_ip_rate_limit", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(integrated_node, "record_macs", lambda *args, **kwargs: None)
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


def _spoofed_g4_payload(miner: str) -> dict:
    return {
        "miner": miner,
        "device": {
            "device_family": "PowerPC",
            "device_arch": "G4",
            "arch": "G4",
            "cores": 8,
            "cpu": "Intel Xeon Platinum",
            "serial_number": f"SERIAL-{miner}",
        },
        "signals": {
            "hostname": "bare-metal-x86-host",
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
                    "data": {
                        "vm_indicators": [],
                        "paths_checked": ["/proc/cpuinfo"],
                        "dmesg_scanned": True,
                    },
                },
            },
            "all_passed": True,
        },
    }


def test_validate_fingerprint_data_accepts_spoofed_g4_without_ppc_evidence():
    payload = _spoofed_g4_payload("spoof-direct")

    passed, reason = integrated_node.validate_fingerprint_data(
        payload["fingerprint"],
        claimed_device=payload["device"],
    )

    assert passed is True
    assert reason == "valid"


def test_attestation_accepts_modern_x86_claiming_g4_and_grants_vintage_weight(attest_client):
    client, db_path = attest_client
    payload = _spoofed_g4_payload("spoof-g4-accepted")

    response = client.post(
        "/attest/submit",
        json=payload,
        headers={"X-Forwarded-For": "198.51.100.25"},
        environ_base={"REMOTE_ADDR": "10.0.0.9"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["fingerprint_passed"] is True

    with sqlite3.connect(db_path) as conn:
        recent = conn.execute(
            "SELECT device_family, device_arch, fingerprint_passed FROM miner_attest_recent WHERE miner = ?",
            (payload["miner"],),
        ).fetchone()
        enrollment = conn.execute(
            "SELECT epoch, weight FROM epoch_enroll WHERE miner_pk = ?",
            (payload["miner"],),
        ).fetchone()

    assert recent == ("PowerPC", "G4", 1)
    assert enrollment == (85, 2.5)
    assert fleet_mod.classify_miner_bucket("g4") == "vintage_powerpc"


def test_bucket_spoof_produces_10x_reward_gain_over_honest_modern_miners():
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)

    miners = [("spoof-g4", "g4")] + [(f"modern-{index}", "modern") for index in range(10)]
    rewards = fleet_mod.calculate_immune_rewards_equal_split(
        db=db,
        epoch=91,
        miners=miners,
        chain_age_years=1.0,
        total_reward_urtc=1_100_000,
    )

    assert rewards["spoof-g4"] == 550_000
    assert rewards["modern-0"] == 55_000
    assert rewards["spoof-g4"] == rewards["modern-0"] * 10
    assert sum(rewards.values()) == 1_100_000
