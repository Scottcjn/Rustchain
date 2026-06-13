import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "bridge_api.py"
BRIDGE_ENV = (
    "RC_BRIDGE_DEFAULT_CONFIRMATIONS",
    "RC_BRIDGE_MAX_CONFIRMATIONS",
    "RC_BRIDGE_LOCK_EXPIRY_SECONDS",
    "RC_BRIDGE_MIN_AMOUNT_RTC",
)


def _load_bridge_api(monkeypatch, **env):
    for name in BRIDGE_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    module_name = f"bridge_api_config_test_{abs(hash(tuple(sorted(env.items()))))}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(module_name, None)


def test_bridge_api_missing_numeric_env_uses_defaults(monkeypatch):
    module = _load_bridge_api(monkeypatch)

    assert module.BRIDGE_DEFAULT_CONFIRMATIONS == 12
    assert module.BRIDGE_MAX_CONFIRMATIONS == 1000
    assert module.BRIDGE_LOCK_EXPIRY_SECONDS == 604800
    assert module.BRIDGE_MIN_AMOUNT_RTC == 1.0


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RC_BRIDGE_DEFAULT_CONFIRMATIONS", "bad"),
        ("RC_BRIDGE_MAX_CONFIRMATIONS", ""),
        ("RC_BRIDGE_LOCK_EXPIRY_SECONDS", "0"),
        ("RC_BRIDGE_MIN_AMOUNT_RTC", "-0.5"),
    ],
)
def test_bridge_api_explicit_bad_numeric_env_fails_closed(monkeypatch, name, value):
    with pytest.raises(ValueError, match=name):
        _load_bridge_api(monkeypatch, **{name: value})


def test_bridge_api_helpers_reject_bad_values_after_import(monkeypatch):
    module = _load_bridge_api(monkeypatch)

    monkeypatch.setenv("RC_BRIDGE_TEST_INT", "nope")
    with pytest.raises(ValueError, match="RC_BRIDGE_TEST_INT"):
        module._env_positive_int("RC_BRIDGE_TEST_INT", 12)
    monkeypatch.setenv("RC_BRIDGE_TEST_FLOAT", "nan")
    with pytest.raises(ValueError, match="RC_BRIDGE_TEST_FLOAT"):
        module._env_positive_float("RC_BRIDGE_TEST_FLOAT", 1.0)


def test_bridge_api_valid_numeric_env_is_preserved(monkeypatch):
    module = _load_bridge_api(
        monkeypatch,
        RC_BRIDGE_DEFAULT_CONFIRMATIONS="6",
        RC_BRIDGE_MAX_CONFIRMATIONS="60",
        RC_BRIDGE_LOCK_EXPIRY_SECONDS="120",
        RC_BRIDGE_MIN_AMOUNT_RTC="0.25",
    )

    assert module.BRIDGE_DEFAULT_CONFIRMATIONS == 6
    assert module.BRIDGE_MAX_CONFIRMATIONS == 60
    assert module.BRIDGE_LOCK_EXPIRY_SECONDS == 120
    assert module.BRIDGE_MIN_AMOUNT_RTC == 0.25
