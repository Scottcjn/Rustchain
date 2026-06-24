import importlib.util
from pathlib import Path


def load_checker_module():
    root = Path(__file__).resolve().parents[2]
    checker_path = root / "rustchain_sdk" / "tools" / "eligibility_checker.py"
    spec = importlib.util.spec_from_file_location("eligibility_checker", checker_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_tls_verification_uses_sdk_safe_default(monkeypatch):
    checker = load_checker_module()
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_epoch_rewards(self, _epoch):
            return {"rewards": []}

        async def get_wallet_balance(self, _miner_id):
            return {"balance": 0}

    monkeypatch.setattr(checker, "RustChainClient", FakeClient)

    checker.asyncio.run(checker.check_eligibility("miner-1", 1, "https://node.example"))

    assert seen["base_url"] == "https://node.example"
    assert seen["verify"] is None


def test_insecure_flag_explicitly_disables_tls_verification(monkeypatch):
    checker = load_checker_module()
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_epoch_rewards(self, _epoch):
            return {"rewards": []}

        async def get_wallet_balance(self, _miner_id):
            return {"balance": 0}

    monkeypatch.setattr(checker, "RustChainClient", FakeClient)

    checker.asyncio.run(
        checker.check_eligibility("miner-1", 1, "https://node.example", insecure_tls=True)
    )

    assert seen["verify"] is False
