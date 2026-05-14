import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "fuzz" / "attestation_fuzzer.py"


def _load_fuzzer_module():
    spec = importlib.util.spec_from_file_location("attestation_fuzzer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mutate_boundary_conditions_replaces_nonce_and_clock_cv(monkeypatch):
    fuzzer = _load_fuzzer_module()
    payload = fuzzer.generate_valid_attestation()
    original_nonce = payload["nonce"]
    original_cv = payload["fingerprint"]["checks"]["clock_drift"]["data"]["cv"]
    choices = iter([-2**63, float("inf")])

    monkeypatch.setattr(fuzzer.random, "choice", lambda values: next(choices))

    mutated = fuzzer.mutate_boundary_conditions(payload)

    assert mutated["nonce"] == -2**63
    assert mutated["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] == float("inf")
    assert payload["nonce"] == original_nonce
    assert payload["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] == original_cv


def test_mutate_boundary_conditions_tolerates_minimal_payload(monkeypatch):
    fuzzer = _load_fuzzer_module()
    payload = {"miner": "minimal"}
    monkeypatch.setattr(fuzzer.random, "choice", lambda values: values[0])

    mutated = fuzzer.mutate_boundary_conditions(payload)

    assert mutated == {"miner": "minimal"}
    assert payload == {"miner": "minimal"}
