# SPDX-License-Identifier: MIT
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "rustchain-telegram-bot" / "bot.py"


class DummyApplication:
    @staticmethod
    def builder():
        return DummyApplication()

    def token(self, *_args, **_kwargs):
        return self

    def build(self):
        return self

    def add_handler(self, *_args, **_kwargs):
        return None

    def run_polling(self, *_args, **_kwargs):
        return None


def load_bot_module(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(RequestException=Exception))
    monkeypatch.setitem(sys.modules, "telegram", SimpleNamespace(Update=SimpleNamespace(ALL_TYPES=object())))
    monkeypatch.setitem(
        sys.modules,
        "telegram.ext",
        SimpleNamespace(
            Application=DummyApplication,
            CommandHandler=lambda *args, **kwargs: (args, kwargs),
            ContextTypes=SimpleNamespace(DEFAULT_TYPE=object),
        ),
    )

    spec = importlib.util.spec_from_file_location("rustchain_telegram_bot", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cmd_miners_uses_paginated_total_and_miner_fallback(monkeypatch):
    module = load_bot_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "api_get",
        lambda path: {
            "miners": [
                {"miner": "alice", "device_arch": "G4", "multiplier": 3, "score": 7},
                {"miner_id": "bob-id", "device_arch": "SPARC", "multiplier": 2, "score": 4},
            ],
            "pagination": {"total": 29, "limit": 2, "offset": 0, "count": 2},
        },
    )
    monkeypatch.setattr(module, "check_rate", lambda _user_id: True)
    replies = []

    class FakeMessage:
        async def reply_text(self, text, **kwargs):
            replies.append((text, kwargs))

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=FakeMessage())

    asyncio.run(module.cmd_miners(update, SimpleNamespace()))

    assert len(replies) == 1
    text, kwargs = replies[0]
    assert kwargs == {"parse_mode": "Markdown"}
    assert "*Active Miners: 29*" in text
    assert "`alice`" in text
    assert "`bob-id`" in text
    assert "... and 27 more" in text
