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
        CREATE TABLE hardware_bindings (
            hardware_id TEXT PRIMARY KEY,
            bound_miner TEXT NOT NULL,
            device_arch TEXT,
            device_model TEXT,
            bound_at INTEGER,
            attestation_count INTEGER DEFAULT 0
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


def _client_fixture(monkeypatch, *, strict_security_path=False):
    local_tmp_dir = Path(__file__).parent / ".tmp_attestation"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_attestation_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "check_ip_rate_limit", lambda client_ip, miner_id: (True, "ok"))
    monkeypatch.setattr(integrated_node, "record_attestation_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "record_macs", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: 85)
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False, raising=False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False, raising=False)
    if not strict_security_path:
        monkeypatch.setattr(integrated_node, "_check_hardware_binding", lambda *args, **kwargs: (True, "ok", ""))

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


@pytest.fixture
def client(monkeypatch):
    yield from _client_fixture(monkeypatch, strict_security_path=False)


@pytest.fixture
def strict_client(monkeypatch):
    yield from _client_fixture(monkeypatch, strict_security_path=True)


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
    ("file_name", "expected_code"),
    [
        ("malformed_device_scalar.json", "INVALID_DEVICE"),
        ("malformed_miner_array.json", "INVALID_MINER"),
        ("malformed_signals_scalar.json", "INVALID_SIGNALS"),
        ("malformed_signals_macs_object.json", "INVALID_SIGNALS_MACS"),
        ("malformed_fingerprint_checks_array.json", "INVALID_FINGERPRINT_CHECKS"),
        ("malformed_report_scalar.json", "INVALID_REPORT"),
    ],
)
def test_attest_submit_rejects_malformed_payload_shapes(client, file_name, expected_code):
    response = _post_raw_json(client, (CORPUS_DIR / file_name).read_text(encoding="utf-8"))

    assert response.status_code in (400, 422)
    assert response.get_json()["ok"] is False
    assert response.get_json()["code"] == expected_code


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"miner": "", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "MISSING_MINER"),
        ({"miner": "   ", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "MISSING_MINER"),
        ({"miner": "fuzz\u200bminer", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_MINER"),
        ({"miner": "'; DROP TABLE balances; --", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_MINER"),
        ({"miner": "f" * 129, "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_MINER"),
        ({"miner": "fuzz-miner", "device": {"cores": "999999999999999999999999"}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_DEVICE_CORES"),
        ({"miner": "fuzz-miner", "device": {"cores": []}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_DEVICE_CORES"),
        ({"miner": "fuzz-miner", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10", None]}, "report": {}}, "INVALID_SIGNALS_MACS"),
        ({"miner": "fuzz-miner", "device": {"cores": 8, "cpu": ["nested"]}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_DEVICE"),
        ({"miner": "fuzz-miner", "device": {"cores": 8}, "signals": {"hostname": ["nested"], "macs": ["AA:BB:CC:DD:EE:10"]}, "report": {}}, "INVALID_SIGNALS"),
        ({"miner": "fuzz-miner", "device": {"cores": 8}, "signals": {"macs": ["AA:BB:CC:DD:EE:10"]}, "report": {"nonce": {"nested": "bad"}}}, "INVALID_REPORT"),
    ],
)
def test_attest_submit_rejects_attack_vector_shapes(client, payload, expected_code):
    response = client.post("/attest/submit", json=payload)

    assert response.status_code in (400, 422)
    assert response.get_json()["ok"] is False
    assert response.get_json()["code"] == expected_code


def test_attest_submit_sql_like_miner_does_not_mutate_schema(client):
    payload = _base_payload()
    payload["miner"] = "'; DROP TABLE balances; --"

    response = client.post("/attest/submit", json=payload)

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_MINER"


def test_validate_fingerprint_data_rejects_non_dict_input():
    passed, reason = integrated_node.validate_fingerprint_data(["not", "a", "dict"])

    assert passed is False
    assert reason == "fingerprint_not_dict"


def test_attest_submit_strict_fixture_rejects_malformed_fingerprint(strict_client):
    payload = _base_payload()
    payload["fingerprint"]["checks"] = []

    response = strict_client.post("/attest/submit", json=payload)

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert response.get_json()["code"] == "INVALID_FINGERPRINT_CHECKS"


def test_attest_submit_strict_fixture_enforces_hardware_binding(strict_client):
    first = _base_payload()
    second = _base_payload()
    second["miner"] = "different-miner"

    first_response = strict_client.post("/attest/submit", json=first)
    second_response = strict_client.post("/attest/submit", json=second)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.get_json()["code"] == "DUPLICATE_HARDWARE"


def _mutate_payload(rng: random.Random) -> dict:
    payload = _base_payload()
    mutation = rng.randrange(14)

    if mutation == 0:
        payload["miner"] = ["not", "a", "string"]
    elif mutation == 1:
        payload["device"] = "not-a-device-object"
    elif mutation == 2:
        payload["device"]["cores"] = rng.choice([0, -1, "NaN", [], {}, "999999999999999999999999"])
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
    elif mutation == 7:
        payload["device"]["cpu"] = rng.choice(["qemu-system-ppc", "IBM POWER8", None, ["nested"]])
        payload["signals"]["hostname"] = rng.choice(["vmware-host", "power8-host", None, ["nested"]])
    elif mutation == 8:
        payload["miner"] = rng.choice(["", " ", "\t", "fuzz\u200bminer", "'; DROP TABLE balances; --"])
    elif mutation == 9:
        payload["miner"] = "f" * 300
    elif mutation == 10:
        payload["device"]["device_family"] = {"nested": {"too": "deep"}}
    elif mutation == 11:
        payload["signals"]["macs"] = ["AA:BB:CC:DD:EE:10", None]
    elif mutation == 12:
        payload["fingerprint"] = ["bad", "shape"]
    else:
        payload["report"]["nonce"] = {"nested": "bad"}

    return payload


def test_attest_submit_mutation_regression_no_unhandled_exceptions(client):
    cases = int(os.getenv("ATTEST_FUZZ_CASES", "250"))
    seed = os.getenv("ATTEST_FUZZ_SEED")
    rng = random.Random(int(seed)) if seed else random.Random()

    for index in range(cases):
        payload = _mutate_payload(rng)
        response = client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"case={index} payload={payload!r}"


# =============================================================================
# Issue #1147 Regression Tests - 500 Crash Fix
# =============================================================================

@pytest.mark.parametrize("malformed_fingerprint", [
    # Non-string bridge_type that could cause AttributeError
    {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}, "bridge_type": None},
    {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}, "bridge_type": 123},
    {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}, "bridge_type": {"nested": "dict"}},
    # Non-string device_arch that could cause AttributeError on .lower()
    {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}, "device_arch": None},
    {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}, "device_arch": 123},
    # Non-list x86_features that could cause issues
    {"checks": {
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        "simd_identity": {"passed": True, "data": {"x86_features": "not-a-list"}}
    }},
    # Empty/malformed checks
    {"checks": None},
    {},
], ids=[
    "bridge_type_none", "bridge_type_int", "bridge_type_dict",
    "device_arch_none", "device_arch_int",
    "x86_features_not_list",
    "checks_none", "checks_empty"
])
def test_validate_fingerprint_data_handles_malformed_inputs_no_crash(malformed_fingerprint):
    """
    FIX #1147: validate_fingerprint_data must handle malformed inputs gracefully
    without raising exceptions that cause 500 errors.
    """
    # Should not raise, should return (False, reason)
    passed, reason = integrated_node.validate_fingerprint_data(malformed_fingerprint)
    assert isinstance(passed, bool)
    assert isinstance(reason, str)
    # Malformed inputs should fail validation
    assert passed is False


def test_attest_submit_no_500_on_malformed_fingerprint(client):
    """
    FIX #1147: The /attest/submit endpoint must never return 500,
    even with malformed fingerprint payloads.
    """
    payload = _base_payload()
    # Inject malformed fingerprint with non-string bridge_type
    payload["fingerprint"] = {
        "checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}},
        "bridge_type": None  # This would previously cause AttributeError
    }
    
    response = client.post("/attest/submit", json=payload)
    
    # Should NEVER be 500 - should be 400/422 for bad input or 200 for accepted
    assert response.status_code < 500, f"Got 500 error with malformed fingerprint"
    data = response.get_json()
    assert "ok" in data or "error" in data


def test_attest_submit_no_500_on_edge_case_architectures(client):
    """
    FIX #1147: Edge case device architectures should not cause crashes.
    """
    payload = _base_payload()
    # Test various non-string arch values
    for bad_arch in [None, 123, [], {}]:
        payload["device"]["device_arch"] = bad_arch
        response = client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 error with device_arch={bad_arch!r}"
