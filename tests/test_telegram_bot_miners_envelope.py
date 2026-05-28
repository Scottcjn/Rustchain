# SPDX-License-Identifier: MIT
import asyncio
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "telegram_bot" / "telegram_bot.py"


def load_bot_module(monkeypatch):
    class FakeInlineQueryResultArticle:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeInputTextMessageContent:
        def __init__(self, text):
            self.text = text

    class FakeApplication:
        @classmethod
        def builder(cls):
            return cls()

        def token(self, _token):
            return self

        def build(self):
            return self

        def add_handler(self, _handler):
            return None

        def run_polling(self):
            return None

    fake_telegram = types.SimpleNamespace(
        Update=object,
        InlineQueryResultArticle=FakeInlineQueryResultArticle,
        InputTextMessageContent=FakeInputTextMessageContent,
    )
    fake_ext = types.SimpleNamespace(
        Application=FakeApplication,
        CommandHandler=lambda *args, **kwargs: (args, kwargs),
        InlineQueryHandler=lambda *args, **kwargs: (args, kwargs),
        ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object),
    )
    fake_aiohttp = types.SimpleNamespace(
        TCPConnector=lambda **kwargs: object(),
        ClientSession=object,
        ClientTimeout=lambda **kwargs: object(),
    )

    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setitem(sys.modules, "telegram", fake_telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", fake_ext)

    spec = importlib.util.spec_from_file_location("telegram_bot_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cmd_miners_renders_paginated_api_envelope(monkeypatch):
    module = load_bot_module(monkeypatch)

    async def fake_fetch(path, params=None):
        assert path == "/api/miners"
        assert params is None
        return {
            "miners": [
                {"miner_id": "alice-id", "device_arch": "G4", "antiquity_multiplier": 3},
                {"miner": "bob", "hardware_type": "SPARC", "antiquity_multiplier": 2},
            ],
            "pagination": {"total": 18, "limit": 2, "offset": 0, "count": 2},
        }

    monkeypatch.setattr(module, "fetch_rustchain", fake_fetch)
    replies = []

    class FakeMessage:
        async def reply_text(self, text, **kwargs):
            replies.append((text, kwargs))

    update = types.SimpleNamespace(message=FakeMessage())

    asyncio.run(module.cmd_miners(update, types.SimpleNamespace()))

    assert len(replies) == 1
    text, kwargs = replies[0]
    assert kwargs["parse_mode"] == "Markdown"
    assert "*Active Miners: 18*" in text
    assert "`alice-id`" in text
    assert "`bob`" in text
    assert "_…and 16 more_" in text


def test_inline_query_uses_paginated_miner_total(monkeypatch):
    module = load_bot_module(monkeypatch)

    async def fake_fetch(path, params=None):
        if path == "/api/miners":
            return {"miners": [{"miner": "alice"}], "pagination": {"total": 9}}
        if path == "/epoch":
            return {"epoch": 12, "slot": 3, "epoch_pot": 4, "enrolled_miners": 9}
        raise AssertionError(path)

    monkeypatch.setattr(module, "fetch_rustchain", fake_fetch)
    monkeypatch.setattr(module, "fetch_price_data", lambda: None)
    answers = []

    class FakeInlineQuery:
        query = "miners"

        async def answer(self, results, **kwargs):
            answers.append((results, kwargs))

    update = types.SimpleNamespace(inline_query=FakeInlineQuery())

    asyncio.run(module.inline_query(update, types.SimpleNamespace()))

    results, kwargs = answers[0]
    assert kwargs == {"cache_time": 30}
    assert results[0].kwargs["title"] == "Active Miners: 9"
    assert results[0].kwargs["input_message_content"].text == "RustChain has 9 active miners."
