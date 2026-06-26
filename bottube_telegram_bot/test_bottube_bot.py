# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("bottube_bot.py")


def _load_bottube_bot(monkeypatch, rate_limit: str, videos_per_page: str):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", rate_limit)
    monkeypatch.setenv("VIDEOS_PER_PAGE", videos_per_page)
    module_name = f"bottube_bot_test_{rate_limit.replace('-', '_')}_{videos_per_page.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_malformed_numeric_env_falls_back_to_defaults(monkeypatch):
    module = _load_bottube_bot(monkeypatch, "not-a-number", "many")

    assert module.RATE_LIMIT_PER_MINUTE == 10
    assert module.VIDEOS_PER_PAGE == 10
    assert module.rate_limiter.max_requests == 10


def test_valid_numeric_env_is_used(monkeypatch):
    module = _load_bottube_bot(monkeypatch, "42", "7")

    assert module.RATE_LIMIT_PER_MINUTE == 42
    assert module.VIDEOS_PER_PAGE == 7
    assert module.rate_limiter.max_requests == 42
