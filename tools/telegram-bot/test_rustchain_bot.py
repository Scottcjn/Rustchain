# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("rustchain_bot.py")


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def _load_bot(monkeypatch, rate_limit: str, price: str):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", rate_limit)
    monkeypatch.setenv("RTC_PRICE_USD", price)

    fake_httpx = types.SimpleNamespace(
        AsyncClient=FakeAsyncClient,
        TimeoutException=TimeoutError,
        HTTPStatusError=Exception,
    )
    fake_telegram = types.SimpleNamespace(BotCommand=object, Update=object)
    fake_ext = types.SimpleNamespace(
        Application=object,
        CommandHandler=lambda *args, **kwargs: (args, kwargs),
        ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object),
    )
    fake_node = types.ModuleType("node")
    fake_tls = types.ModuleType("node.tls_config")
    fake_tls.get_async_tls_verify = lambda: True

    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setitem(sys.modules, "telegram", fake_telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", fake_ext)
    monkeypatch.setitem(sys.modules, "node", fake_node)
    monkeypatch.setitem(sys.modules, "node.tls_config", fake_tls)

    module_name = f"rustchain_bot_env_test_{rate_limit.replace('-', '_')}_{price.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_malformed_numeric_env_falls_back_to_defaults(monkeypatch):
    module = _load_bot(monkeypatch, "fast", "cheap")

    assert module.RATE_LIMIT_RPM == 10
    assert module.RTC_PRICE_USD == 0.10


def test_valid_numeric_env_is_used(monkeypatch):
    module = _load_bot(monkeypatch, "25", "0.42")

    assert module.RATE_LIMIT_RPM == 25
    assert module.RTC_PRICE_USD == 0.42
