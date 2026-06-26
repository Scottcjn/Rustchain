# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("rustchain_query_bot.py")


def _load_query_bot(monkeypatch, rate_limit: str):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", rate_limit)
    module_name = f"rustchain_query_bot_test_{rate_limit.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_malformed_rate_limit_env_falls_back_to_default(monkeypatch):
    module = _load_query_bot(monkeypatch, "not-a-number")

    assert module.RATE_LIMIT_PER_MINUTE == 10
    assert module.rate_limiter.max_requests == 10


def test_valid_rate_limit_env_is_used(monkeypatch):
    module = _load_query_bot(monkeypatch, "42")

    assert module.RATE_LIMIT_PER_MINUTE == 42
    assert module.rate_limiter.max_requests == 42
