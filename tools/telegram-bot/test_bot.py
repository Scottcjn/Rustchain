# SPDX-License-Identifier: Apache-2.0
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("bot.py")


def install_telegram_stubs(monkeypatch):
    telegram = types.ModuleType("telegram")

    class BotCommand:
        def __init__(self, name, description):
            self.name = name
            self.description = description

    class Update:
        ALL_TYPES = object()

    telegram.BotCommand = BotCommand
    telegram.Update = Update

    telegram_ext = types.ModuleType("telegram.ext")

    class _Builder:
        def token(self, _token):
            return self

        def build(self):
            return object()

    class Application:
        @classmethod
        def builder(cls):
            return _Builder()

    class CommandHandler:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class ContextTypes:
        DEFAULT_TYPE = object()

    telegram_ext.Application = Application
    telegram_ext.CommandHandler = CommandHandler
    telegram_ext.ContextTypes = ContextTypes
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", telegram_ext)


def load_bot_module(monkeypatch):
    install_telegram_stubs(monkeypatch)
    module_name = "test_tools_telegram_bot_module"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_malformed_numeric_env_falls_back(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "not-an-int")
    monkeypatch.setenv("RTC_PRICE_USD", "not-a-float")

    module = load_bot_module(monkeypatch)

    assert module.RATE_LIMIT_RPM == 10
    assert module.RTC_PRICE_USD == 0.10


def test_valid_numeric_env_is_preserved(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "42")
    monkeypatch.setenv("RTC_PRICE_USD", "0.25")

    module = load_bot_module(monkeypatch)

    assert module.RATE_LIMIT_RPM == 42
    assert module.RTC_PRICE_USD == 0.25
