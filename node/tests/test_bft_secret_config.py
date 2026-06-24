import importlib.util
from pathlib import Path

import pytest


def load_bft_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "rustchain_bft_consensus.py"
    spec = importlib.util.spec_from_file_location("rustchain_bft_consensus", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bft_secret_requires_explicit_configuration(monkeypatch):
    module = load_bft_module()
    monkeypatch.delenv("RUSTCHAIN_BFT_SECRET", raising=False)

    with pytest.raises(ValueError, match="RUSTCHAIN_BFT_SECRET"):
        module._load_bft_secret()


def test_bft_secret_prefers_cli_secret(monkeypatch):
    module = load_bft_module()
    monkeypatch.setenv("RUSTCHAIN_BFT_SECRET", "env-secret")

    assert module._load_bft_secret("cli-secret") == "cli-secret"


def test_bft_secret_uses_environment(monkeypatch):
    module = load_bft_module()
    monkeypatch.setenv("RUSTCHAIN_BFT_SECRET", "env-secret")

    assert module._load_bft_secret() == "env-secret"
