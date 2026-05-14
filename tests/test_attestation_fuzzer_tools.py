# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain attestation fuzz harness helpers."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "fuzz" / "attestation_fuzzer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("attestation_fuzzer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generators_return_independent_payload_shapes(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(module.random, "randint", lambda low, _high: low)

    valid = module.generate_valid_attestation()
    minimal = module.generate_minimal_attestation()
    complex_payload = module.generate_complex_attestation()

    assert valid is not module.BASE_ATTESTATION
    assert valid["miner"].startswith("fuzz-wallet-")
    assert valid["miner_id"].startswith("fuzz-miner-")
    assert valid["device"]["device_id"].startswith("fuzz-dev-")
    assert valid["signals"]["macs"][0].count(":") == 5
    assert set(minimal) == {"miner", "miner_id", "nonce"}
    assert complex_payload["report"]["extra_cpu_info"]["cores"] == 1
    assert "rom_fingerprint" in complex_payload["fingerprint"]["checks"]
    assert "extra_cpu_info" not in module.BASE_ATTESTATION["report"]


def test_mutation_strategies_change_expected_fields(monkeypatch):
    module = load_module()
    payload = module._deep_copy(module.BASE_ATTESTATION)
    monkeypatch.setattr(module.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(module.random, "randint", lambda low, _high: low)

    type_confused = module.mutate_type_confusion(payload)
    missing = module.mutate_missing_fields(payload)
    oversized = module.mutate_oversized_values(payload)
    boundary = module.mutate_boundary_conditions(payload)
    nested = module.mutate_nested_structures(payload)
    mismatch = module.mutate_boolean_dict_mismatch(payload)
    timestamped = module.mutate_timestamp_edge_cases(payload)
    encoded = module.mutate_encoding_corruption(payload)

    assert isinstance(type_confused["nonce"], str)
    assert isinstance(type_confused["miner"], int)
    assert "miner" not in missing
    assert len(oversized["miner"]) == 10_000
    assert len(oversized["signals"]["macs"]) == 500
    assert boundary["nonce"] == 0
    assert boundary["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] == 0
    cursor = nested
    for i in range(100):
        cursor = cursor[f"level_{i}"]
    assert mismatch["fingerprint"] is True
    assert timestamped["nonce"] == -1
    assert encoded["miner"] == "\x00\x01\x02\x03"
    assert payload == module.BASE_ATTESTATION


def test_submit_payload_offline_and_http_paths_save_expected_corpus(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    harness = module.AttestationFuzzHarness(offline=True)
    payload = {"miner": "alice", "nonce": 1}

    result = harness.submit_payload(payload)

    assert result.crashed is False
    assert result.status_code is None
    assert result.exception is None
    saved = tmp_path / module.CORPUS_DIR / f"{result.payload_hash}.json"
    assert json.loads(saved.read_text())["payload"] == payload

    response = Mock(status_code=503, text="server exploded")
    http_harness = module.AttestationFuzzHarness(node_url="http://node.test")
    with patch.object(module.requests, "post", return_value=response) as post:
        crashed = http_harness.submit_payload(payload, timeout=3)

    assert crashed.crashed is True
    assert crashed.status_code == 503
    assert crashed.exception == "HTTP 503: server exploded"
    post.assert_called_once_with(
        "http://node.test",
        json=payload,
        timeout=3,
        verify=False,
    )
    assert (tmp_path / module.CRASH_DIR / f"{crashed.payload_hash}.json").exists()


def test_load_crash_corpus_and_minimize_keep_crashing_fields(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    harness = module.AttestationFuzzHarness(offline=True)
    crash_file = tmp_path / module.CRASH_DIR / "case.json"
    crash_file.write_text(json.dumps({"payload": {"keep": True}}))
    (tmp_path / module.CRASH_DIR / "bad.json").write_text("{")

    assert harness.load_crash_corpus() == [{"keep": True}]

    crashing_keys = []

    def fake_submit(payload):
        crashed = "keep" in payload
        if crashed:
            crashing_keys.append(set(payload))
        return module.FuzzResult(
            payload=payload,
            crashed=crashed,
            status_code=None,
            exception="boom" if crashed else None,
            duration=0.0,
            payload_hash="hash",
        )

    harness.submit_payload = fake_submit
    minimized = harness.minimize({"drop": 1, "keep": {"inner": 2, "remove": 3}})

    assert minimized == {"keep": {}}
    assert {"drop", "keep"} in crashing_keys
