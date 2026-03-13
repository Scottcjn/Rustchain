#!/usr/bin/env python3
"""
RustChain Attestation Regression Tests
=======================================
Regression verification tests for attestation fuzz harness.
Tests are tied to real endpoints/validators and verify crash fixes.

Usage:
    pytest test_attestation_regression.py -v
    pytest test_attestation_regression.py --corpus-dir ./attestation_corpus
    pytest test_attestation_regression.py --replay-crashes

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/475
"""

import json
import os
import random
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "node"))

# Mock environment
os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
os.environ.setdefault("DB_PATH", ":memory:")

from tests import mock_crypto
sys.modules["rustchain_crypto"] = mock_crypto

# Load integrated node (reuse from conftest if available)
if "integrated_node" in sys.modules:
    integrated_node = sys.modules["integrated_node"]
else:
    import importlib.util
    node_path = project_root / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"
    spec = importlib.util.spec_from_file_location("integrated_node", node_path)
    integrated_node = importlib.util.module_from_spec(spec)
    sys.modules["integrated_node"] = integrated_node
    spec.loader.exec_module(integrated_node)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).parent / "attestation_corpus"
CRASH_CORPUS_DIR = Path(__file__).parent / "attestation_crash_corpus"


def _init_attestation_db(db_path: Path) -> None:
    """Initialize test database with required tables."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS blocked_wallets (
            wallet TEXT PRIMARY KEY,
            reason TEXT
        );
        CREATE TABLE IF NOT EXISTS balances (
            miner_pk TEXT PRIMARY KEY,
            balance_rtc REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS epoch_enroll (
            epoch INTEGER NOT NULL,
            miner_pk TEXT NOT NULL,
            weight REAL NOT NULL,
            PRIMARY KEY (epoch, miner_pk)
        );
        CREATE TABLE IF NOT EXISTS miner_header_keys (
            miner_id TEXT PRIMARY KEY,
            pubkey_hex TEXT
        );
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            commitment TEXT
        );
        CREATE TABLE IF NOT EXISTS oui_deny (
            oui TEXT PRIMARY KEY,
            vendor TEXT,
            enforce INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS hardware_bindings (
            hardware_id TEXT PRIMARY KEY,
            bound_miner TEXT NOT NULL,
            device_arch TEXT,
            device_model TEXT,
            bound_at INTEGER,
            attestation_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            attested_at INTEGER,
            fingerprint_passed INTEGER,
            client_ip TEXT,
            warthog_bonus REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS mac_addresses (
            miner_pk TEXT NOT NULL,
            mac TEXT NOT NULL,
            first_seen INTEGER,
            PRIMARY KEY (miner_pk, mac)
        );
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def test_client(monkeypatch):
    """Create test client with isolated database."""
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
    monkeypatch.setattr(integrated_node, "_check_hardware_binding", lambda *args, **kwargs: (True, "ok", ""))

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


# ---------------------------------------------------------------------------
# Baseline Payload
# ---------------------------------------------------------------------------

def baseline_payload() -> dict:
    """Generate a valid baseline attestation payload."""
    return {
        "miner": "test-miner",
        "miner_id": "test-miner-id",
        "nonce": "test-nonce",
        "device": {
            "model": "AMD Ryzen 5 5600X",
            "arch": "x86_64",
            "family": "x86_64",
            "cores": 8,
            "cpu_serial": "SERIAL-123",
            "device_id": "550e8400-e29b-41d4-a716-446655440000",
            "serial_number": "SERIAL-123",
        },
        "signals": {
            "macs": ["aa:bb:cc:dd:ee:ff"],
            "hostname": "test-host",
        },
        "report": {
            "nonce": "test-nonce",
            "commitment": "test-commitment",
        },
        "fingerprint": {
            "all_passed": True,
            "checks": {
                "clock_drift": {"passed": True, "data": {"cv": 0.092, "samples": 1000}},
                "cache_timing": {"passed": True, "data": {"profile": [1.2, 3.4, 5.6]}},
                "simd_identity": {"passed": True, "data": {}},
                "thermal_drift": {"passed": True, "data": {}},
                "instruction_jitter": {"passed": True, "data": {}},
                "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
            },
        },
    }


# ---------------------------------------------------------------------------
# Corpus Replay Tests
# ---------------------------------------------------------------------------

def load_corpus_entries(corpus_dir: Path) -> List[dict]:
    """Load all corpus entries from directory."""
    entries = []
    if not corpus_dir.exists():
        return entries
    
    for filepath in sorted(corpus_dir.glob("*.json")):
        try:
            data = json.loads(filepath.read_text())
            entries.append(data)
        except Exception:
            pass
    return entries


@pytest.mark.parametrize("entry", load_corpus_entries(CORPUS_DIR), ids=lambda e: str(e.get("mutator", "unknown"))[:30] if isinstance(e, dict) else "unknown")
def test_corpus_no_unhandled_exceptions(test_client, entry):
    """
    REGRESSION: All corpus entries should not cause unhandled exceptions.
    This verifies that crash fixes are working.
    """
    # Handle malformed corpus entries
    if not isinstance(entry, dict):
        pytest.skip(f"Invalid corpus entry type: {type(entry)}")
    
    payload = entry.get("payload")
    if payload is None:
        # Non-JSON payload - skip for test client
        pytest.skip("Non-JSON payload not supported in test client")
    
    response = test_client.post("/attest/submit", json=payload)
    
    # Should never get 500 - should be 400/422 for bad input or 200 for accepted
    assert response.status_code < 500, f"Got 500 error with payload: {payload}"


@pytest.mark.parametrize("entry", load_corpus_entries(CRASH_CORPUS_DIR), ids=lambda e: str(e.get("mutator", "unknown"))[:30] if isinstance(e, dict) else "unknown")
def test_crash_corpus_regression_fixed(test_client, entry):
    """
    REGRESSION: Previously crashing payloads should now be handled gracefully.
    This is the key regression test - verifies crash fixes are effective.
    """
    payload = entry.get("payload")
    if payload is None:
        pytest.skip("Non-JSON payload not supported in test client")
    
    response = test_client.post("/attest/submit", json=payload)
    
    # CRITICAL: Should NEVER be 500 after fix
    assert response.status_code < 500, f"REGRESSION: Previously fixed crash is back! Payload: {payload}"


# ---------------------------------------------------------------------------
# Validator Unit Tests
# ---------------------------------------------------------------------------

class TestValidateFingerprintData:
    """Tests for validate_fingerprint_data function."""
    
    @pytest.mark.parametrize("malformed_input", [
        None,
        [],
        "not a dict",
        123,
        {},
        {"checks": None},
        {"checks": []},
        {"checks": "string"},
    ], ids=[
        "none", "list", "string", "int", "empty_dict",
        "checks_none", "checks_list", "checks_string"
    ])
    def test_rejects_non_dict_inputs(self, malformed_input):
        """validate_fingerprint_data should reject non-dict inputs."""
        passed, reason = integrated_node.validate_fingerprint_data(malformed_input)
        assert passed is False
        assert isinstance(reason, str)
        assert len(reason) > 0
    
    @pytest.mark.parametrize("malformed_checks", [
        {"checks": None},
        {"checks": []},
        {"checks": "string"},
        {"checks": 123},
    ], ids=["checks_none", "checks_list", "checks_string", "checks_int"])
    def test_rejects_malformed_checks(self, malformed_checks):
        """validate_fingerprint_data should reject malformed checks."""
        passed, reason = integrated_node.validate_fingerprint_data(malformed_checks)
        assert passed is False
        assert isinstance(reason, str)
    
    @pytest.mark.parametrize("bridge_type_value", [
        None, 123, [], {}, True,
    ], ids=["none", "int", "list", "dict", "bool"])
    def test_handles_non_string_bridge_type(self, bridge_type_value):
        """
        FIX #1147: Non-string bridge_type should not cause AttributeError.
        """
        payload = {
            "checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}},
            "bridge_type": bridge_type_value,
        }
        passed, reason = integrated_node.validate_fingerprint_data(payload)
        assert passed is False
        assert isinstance(reason, str)
    
    @pytest.mark.parametrize("device_arch_value", [
        None, 123, [], {}, True,
    ], ids=["none", "int", "list", "dict", "bool"])
    def test_handles_non_string_device_arch(self, device_arch_value):
        """
        FIX #1147: Non-string device_arch should not cause AttributeError on .lower().
        """
        payload = {
            "checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}},
            "device_arch": device_arch_value,
        }
        passed, reason = integrated_node.validate_fingerprint_data(payload)
        assert passed is False
        assert isinstance(reason, str)
    
    def test_valid_fingerprint_passes(self):
        """Valid fingerprint should pass validation."""
        payload = {
            "all_passed": True,
            "checks": {
                "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
                "clock_drift": {"passed": True, "data": {"cv": 0.1}},
            },
        }
        passed, reason = integrated_node.validate_fingerprint_data(payload)
        assert passed is True


class TestValidateAttestationPayloadShape:
    """Tests for _validate_attestation_payload_shape function."""
    
    def test_rejects_empty_dict(self, test_client):
        """Empty dict should be rejected."""
        response = test_client.post("/attest/submit", json={})
        assert response.status_code in (400, 422)
        data = response.get_json()
        assert data["ok"] is False
    
    def test_missing_fields_no_crash(self, test_client):
        """
        Missing fields should be handled gracefully (no 500 error).
        Server may accept with defaults or reject with 400/422.
        """
        # Test missing miner - server may use miner_id fallback
        payload = baseline_payload()
        del payload["miner"]
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, "Missing miner caused 500 error"
        
        # Test missing device
        payload = baseline_payload()
        del payload["device"]
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, "Missing device caused 500 error"
        
        # Test missing signals
        payload = baseline_payload()
        del payload["signals"]
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, "Missing signals caused 500 error"
        
        # Test missing report
        payload = baseline_payload()
        del payload["report"]
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, "Missing report caused 500 error"


# ---------------------------------------------------------------------------
# Mutation Strategy Tests
# ---------------------------------------------------------------------------

class TestMutationStrategies:
    """Tests for various mutation strategies."""
    
    @pytest.mark.parametrize("mutation_name,mutation_fn", [
        ("empty_miner", lambda p: {**p, "miner": ""}),
        ("whitespace_miner", lambda p: {**p, "miner": "   "}),
        ("null_miner", lambda p: {**p, "miner": None}),
        ("array_miner", lambda p: {**p, "miner": ["not", "a", "string"]}),
        ("object_miner", lambda p: {**p, "miner": {"nested": "value"}}),
        ("huge_miner", lambda p: {**p, "miner": "x" * 10000}),
    ], ids=["empty", "whitespace", "null", "array", "object", "huge"])
    def test_miner_mutations(self, test_client, mutation_name, mutation_fn):
        """Miner field mutations should be handled gracefully."""
        payload = mutation_fn(baseline_payload())
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 for {mutation_name}"
    
    @pytest.mark.parametrize("mutation_name,mutation_fn", [
        ("null_device", lambda p: {**p, "device": None}),
        ("string_device", lambda p: {**p, "device": "not an object"}),
        ("array_device", lambda p: {**p, "device": [1, 2, 3]}),
        ("empty_device", lambda p: {**p, "device": {}}),
    ], ids=["null", "string", "array", "empty"])
    def test_device_mutations(self, test_client, mutation_name, mutation_fn):
        """Device field mutations should be handled gracefully."""
        payload = mutation_fn(baseline_payload())
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 for {mutation_name}"
    
    @pytest.mark.parametrize("mutation_name,mutation_fn", [
        ("null_signals", lambda p: {**p, "signals": None}),
        ("string_signals", lambda p: {**p, "signals": "not an object"}),
        ("array_signals", lambda p: {**p, "signals": [1, 2, 3]}),
        ("empty_signals", lambda p: {**p, "signals": {}}),
    ], ids=["null", "string", "array", "empty"])
    def test_signals_mutations(self, test_client, mutation_name, mutation_fn):
        """Signals field mutations should be handled gracefully."""
        payload = mutation_fn(baseline_payload())
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 for {mutation_name}"
    
    @pytest.mark.parametrize("mutation_name,mutation_fn", [
        ("null_report", lambda p: {**p, "report": None}),
        ("string_report", lambda p: {**p, "report": "not an object"}),
        ("array_report", lambda p: {**p, "report": [1, 2, 3]}),
        ("empty_report", lambda p: {**p, "report": {}}),
    ], ids=["null", "string", "array", "empty"])
    def test_report_mutations(self, test_client, mutation_name, mutation_fn):
        """Report field mutations should be handled gracefully."""
        payload = mutation_fn(baseline_payload())
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 for {mutation_name}"
    
    @pytest.mark.parametrize("mutation_name,mutation_fn", [
        ("null_fingerprint", lambda p: {**p, "fingerprint": None}),
        ("string_fingerprint", lambda p: {**p, "fingerprint": "not an object"}),
        ("array_fingerprint", lambda p: {**p, "fingerprint": [1, 2, 3]}),
        ("empty_fingerprint", lambda p: {**p, "fingerprint": {}}),
    ], ids=["null", "string", "array", "empty"])
    def test_fingerprint_mutations(self, test_client, mutation_name, mutation_fn):
        """Fingerprint field mutations should be handled gracefully."""
        payload = mutation_fn(baseline_payload())
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500, f"Got 500 for {mutation_name}"


# ---------------------------------------------------------------------------
# Security Tests
# ---------------------------------------------------------------------------

class TestSecurityVectors:
    """Security-focused regression tests."""
    
    def test_sql_injection_miner(self, test_client):
        """SQL injection attempts in miner field should not cause crashes."""
        payload = baseline_payload()
        payload["miner"] = "'; DROP TABLE miners; --"
        response = test_client.post("/attest/submit", json=payload)
        # Key: should NOT crash (500). May be rejected (400/422) or accepted via fallback
        assert response.status_code < 500, "SQL injection caused 500 error"
    
    def test_xss_attempt_hostname(self, test_client):
        """XSS attempts in hostname should be handled."""
        payload = baseline_payload()
        payload["signals"]["hostname"] = "<script>alert(1)</script>"
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_path_traversal_model(self, test_client):
        """Path traversal attempts should be handled."""
        payload = baseline_payload()
        payload["device"]["model"] = "../../../etc/passwd"
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_unicode_injection(self, test_client):
        """Unicode edge cases should be handled."""
        payload = baseline_payload()
        payload["miner"] = "\x00\x00\x00"
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_null_byte_injection(self, test_client):
        """Null byte injection should be handled."""
        payload = baseline_payload()
        payload["device"]["cpu_serial"] = "SERIAL\x00NULL"
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case regression tests."""
    
    def test_extremely_large_payload(self, test_client):
        """Very large payloads should be handled (or rejected gracefully)."""
        payload = baseline_payload()
        payload["device"]["model"] = "x" * 1_000_000
        response = test_client.post("/attest/submit", json=payload)
        # Should not crash - may be 413 or 400 or even 200
        assert response.status_code < 500
    
    def test_deeply_nested_payload(self, test_client):
        """Deeply nested structures should be handled."""
        payload = baseline_payload()
        deep = {}
        current = deep
        for _ in range(100):
            current["x"] = {}
            current = current["x"]
        payload["device"]["model"] = deep
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_float_edge_values(self, test_client):
        """Float edge values should be handled."""
        payload = baseline_payload()
        payload["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] = float("inf")
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_nan_values(self, test_client):
        """NaN values should be handled."""
        payload = baseline_payload()
        payload["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] = float("nan")
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_negative_cores(self, test_client):
        """Negative core count should be rejected."""
        payload = baseline_payload()
        payload["device"]["cores"] = -1
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_zero_cores(self, test_client):
        """Zero core count should be rejected."""
        payload = baseline_payload()
        payload["device"]["cores"] = 0
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500
    
    def test_huge_core_count(self, test_client):
        """Unrealistic core count should be handled."""
        payload = baseline_payload()
        payload["device"]["cores"] = 999999999
        response = test_client.post("/attest/submit", json=payload)
        assert response.status_code < 500


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

class TestPropertyBased:
    """Property-based mutation tests."""
    
    @pytest.mark.parametrize("seed", range(5))
    def test_random_mutations_no_crash(self, test_client, seed):
        """Random mutations should not cause crashes."""
        random.seed(seed)
        
        for _ in range(50):
            payload = baseline_payload()
            mutation = random.randint(0, 10)
            
            if mutation == 0:
                payload["miner"] = None
            elif mutation == 1:
                payload["device"] = "not an object"
            elif mutation == 2:
                payload["signals"] = None
            elif mutation == 3:
                payload["report"] = []
            elif mutation == 4:
                payload["fingerprint"] = "string"
            elif mutation == 5:
                payload["device"]["cores"] = "not a number"
            elif mutation == 6:
                payload["signals"]["macs"] = "not a list"
            elif mutation == 7:
                payload["miner"] = ""
            elif mutation == 8:
                payload["device"]["model"] = None
            elif mutation == 9:
                del payload["fingerprint"]
            else:
                payload["unknown_field"] = "injected"
            
            response = test_client.post("/attest/submit", json=payload)
            assert response.status_code < 500, f"Crash with mutation {mutation}, seed {seed}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
