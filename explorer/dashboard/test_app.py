# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("app.py")


def _load_dashboard(monkeypatch, port: str, timeout: str):
    monkeypatch.setenv("PORT", port)
    monkeypatch.setenv("RUSTCHAIN_API_TIMEOUT", timeout)
    module_name = f"explorer_dashboard_app_test_{port.replace('-', '_')}_{timeout.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_malformed_numeric_env_falls_back_to_defaults(monkeypatch):
    module = _load_dashboard(monkeypatch, "bad-port", "slow")

    assert module._int_env("PORT", 8787) == 8787
    assert module.TIMEOUT == 8.0


def test_valid_numeric_env_is_used(monkeypatch):
    module = _load_dashboard(monkeypatch, "9090", "2.5")

    assert module._int_env("PORT", 8787) == 9090
    assert module.TIMEOUT == 2.5
