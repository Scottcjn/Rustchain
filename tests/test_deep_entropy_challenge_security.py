# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEEP_ENTROPY_PATH = REPO_ROOT / "rips" / "python" / "rustchain" / "deep_entropy.py"


def load_deep_entropy():
    spec = importlib.util.spec_from_file_location("deep_entropy_under_test", DEEP_ENTROPY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_challenge_uses_secrets_for_nonce_and_operations(monkeypatch):
    deep_entropy = load_deep_entropy()
    randbelow_bounds = []

    def fake_randbelow(bound):
        randbelow_bounds.append(bound)
        return 0

    monkeypatch.setattr(deep_entropy.secrets, "token_bytes", lambda size: b"\xab" * size)
    monkeypatch.setattr(deep_entropy.secrets, "randbelow", fake_randbelow)

    challenge = deep_entropy.DeepEntropyVerifier().generate_challenge()

    assert challenge["nonce"] == "ab" * 32
    assert len(challenge["operations"]) == 100
    assert randbelow_bounds.count(1_000_000) == 50
    assert randbelow_bounds.count(1_000) == 25
    assert randbelow_bounds.count(5) == 25
    assert challenge["operations"][:4] == [
        {"op": "mul", "value": 1},
        {"op": "div", "value": 1},
        {"op": "fadd", "value": 0.0},
        {"op": "memory", "stride": 1},
    ]
