import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "auto_epoch_settler.py"


def _load_settler(monkeypatch, **env):
    for name in ("RUSTCHAIN_SETTLE_INTERVAL", "RUSTCHAIN_SLOTS_PER_EPOCH"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    module_name = f"auto_epoch_settler_config_test_{abs(hash(tuple(sorted(env.items()))))}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(module_name, None)


def test_auto_epoch_settler_bad_numeric_env_falls_back(monkeypatch):
    module = _load_settler(
        monkeypatch,
        RUSTCHAIN_SETTLE_INTERVAL="not-an-int",
        RUSTCHAIN_SLOTS_PER_EPOCH="also-bad",
    )

    assert module.CHECK_INTERVAL == 300
    assert module.SLOTS_PER_EPOCH == 144


def test_auto_epoch_settler_non_positive_env_falls_back(monkeypatch):
    module = _load_settler(
        monkeypatch,
        RUSTCHAIN_SETTLE_INTERVAL="0",
        RUSTCHAIN_SLOTS_PER_EPOCH="-9",
    )

    assert module.CHECK_INTERVAL == 300
    assert module.SLOTS_PER_EPOCH == 144


def test_auto_epoch_settler_valid_numeric_env_is_preserved(monkeypatch):
    module = _load_settler(
        monkeypatch,
        RUSTCHAIN_SETTLE_INTERVAL="45",
        RUSTCHAIN_SLOTS_PER_EPOCH="72",
    )

    assert module.CHECK_INTERVAL == 45
    assert module.SLOTS_PER_EPOCH == 72
