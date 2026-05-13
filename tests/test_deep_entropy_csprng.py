import importlib.util
import sys
from pathlib import Path


DEEP_ENTROPY_PATH = (
    Path(__file__).resolve().parents[1] / "rips" / "python" / "rustchain" / "deep_entropy.py"
)


def load_deep_entropy_module():
    spec = importlib.util.spec_from_file_location("deep_entropy_test_module", DEEP_ENTROPY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeCSPRNG:
    def __init__(self):
        self.randint_calls = []
        self.uniform_calls = []
        self.choice_calls = []

    def randint(self, low, high):
        self.randint_calls.append((low, high))
        return high

    def uniform(self, low, high):
        self.uniform_calls.append((low, high))
        return high / 2

    def choice(self, values):
        self.choice_calls.append(tuple(values))
        return values[-1]


def test_generate_challenge_uses_csprng_nonce_and_operations(monkeypatch):
    deep_entropy = load_deep_entropy_module()
    fake_rng = FakeCSPRNG()
    monkeypatch.setattr(deep_entropy, "_CSPRNG", fake_rng)
    monkeypatch.setattr(deep_entropy.secrets, "token_bytes", lambda size: b"\xab" * size)
    monkeypatch.setattr(deep_entropy.time, "time", lambda: 1234567890.9)

    challenge = deep_entropy.DeepEntropyVerifier().generate_challenge()

    assert challenge["nonce"] == (b"\xab" * 32).hex()
    assert challenge["timestamp"] == 1234567890
    assert challenge["expires_at"] == 1234568190
    assert len(challenge["operations"]) == 100
    assert len(fake_rng.randint_calls) == 50
    assert len(fake_rng.uniform_calls) == 25
    assert len(fake_rng.choice_calls) == 25
    assert ("mul", 1000000) in [
        (op["op"], op.get("value")) for op in challenge["operations"]
    ]
    assert ("memory", 256) in [
        (op["op"], op.get("stride")) for op in challenge["operations"]
    ]
