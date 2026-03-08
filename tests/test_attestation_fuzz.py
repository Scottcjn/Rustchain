import json
import os
import random
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

integrated_node = sys.modules["integrated_node"]

CORPUS_DIR = Path(__file__).parent / "attestation_corpus"


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


def _base_payload() -> dict:
    return {
        "miner": "fuzz-miner",
        "device": {
            "device_family": "PowerPC",
            "device_arch": "power8",
            "cores": 8,
            "cpu": "IBM POWER8",
            "serial_number": "SERIAL-123",
        },
        "signals": {
            "hostname": "power8-host",
            "macs": ["AA:BB:CC:DD:EE:10"],
        },
        "report": {
            "nonce": "nonce-123",
            "commitment": "commitment-123",
        },
        "fingerprint": {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"]},
                },
                "clock_drift": {
                    "passed": True,
                    "data": {"drift_ms": 0},
                },
            }
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
    monkeypatch.setattr(integrated_node, "check_ip_rate_limit", lambda client_ip, miner_id: (True, "ok"))
    monkeypatch.setattr(integrated_node, "_check_hardware_binding", lambda *args, **kwargs: (True, "ok", ""))
    monkeypatch.setattr(integrated_node, "record_attestation_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "record_macs", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: 85)

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def _post_raw_json(client, raw_json: str):
    return client.post("/attest/submit", data=raw_json, content_type="application/json")


@pytest.mark.parametrize(
    ("file_name", "expected_status"),
    [
        ("invalid_root_null.json", 400),
        ("invalid_root_array.json", 400),
    ],
)
def test_attest_submit_rejects_non_object_json(client, file_name, expected_status):
    response = _post_raw_json(client, (CORPUS_DIR / file_name).read_text(encoding="utf-8"))

    assert response.status_code == expected_status
    data = response.get_json()
    assert data["code"] == "INVALID_JSON_OBJECT"


@pytest.mark.parametrize(
    "file_name",
    [
        "malformed_device_scalar.json",
        "malformed_signals_scalar.json",
        "malformed_signals_macs_object.json",
        "malformed_fingerprint_checks_array.json",
    ],
)
def test_attest_submit_corpus_cases_do_not_raise_server_errors(client, file_name):
    response = _post_raw_json(client, (CORPUS_DIR / file_name).read_text(encoding="utf-8"))

    assert response.status_code < 500
    assert response.get_json()["ok"] is True


def _mutate_payload(rng: random.Random) -> dict:
    payload = _base_payload()
    mutation = rng.randrange(8)

    if mutation == 0:
        payload["miner"] = ["not", "a", "string"]
    elif mutation == 1:
        payload["device"] = "not-a-device-object"
    elif mutation == 2:
        payload["device"]["cores"] = rng.choice([0, -1, "NaN", [], {}])
    elif mutation == 3:
        payload["signals"] = "not-a-signals-object"
    elif mutation == 4:
        payload["signals"]["macs"] = rng.choice(
            [
                {"primary": "AA:BB:CC:DD:EE:99"},
                "AA:BB:CC:DD:EE:99",
                [None, 123, "AA:BB:CC:DD:EE:99"],
            ]
        )
    elif mutation == 5:
        payload["report"] = rng.choice(["not-a-report-object", [], {"commitment": ["bad"]}])
    elif mutation == 6:
        payload["fingerprint"] = {"checks": rng.choice([[], "bad", {"anti_emulation": True}])}
    else:
        payload["device"]["cpu"] = rng.choice(["qemu-system-ppc", "IBM POWER8", None, ["nested"]])
        payload["signals"]["hostname"] = rng.choice(["vmware-host", "power8-host", None, ["nested"]])

    return payload


def test_attest_submit_fuzz_no_unhandled_exceptions(client):
    cases = int(os.getenv("ATTEST_FUZZ_CASES", "250"))
    rng = random.Random(475)

    for index in range(cases):
        payload = _mutate_payload(rng)
        response = client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"case={index} payload={payload!r}"
