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


def test_parse_raydium_mint_price_payload(monkeypatch):
    module = load_bot_module(monkeypatch)

    price = module.parse_raydium_mint_price(
        {
            "success": True,
            "data": {
                module.WRTC_MINT: "0.10214647024163659",
            },
        }
    )

    assert price == 0.10214647024163659


def test_parse_raydium_pool_info_for_wrapped_rtc_pair(monkeypatch):
    module = load_bot_module(monkeypatch)

    pool = module.parse_raydium_pool_info(
        {
            "success": True,
            "data": {
                "data": [
                    {
                        "id": "unrelated-pool",
                        "mintA": {"address": module.WSOL_MINT},
                        "mintB": {"address": "other-token"},
                        "price": 99,
                        "tvl": 999999,
                        "day": {"volume": 999999},
                    },
                    {
                        "id": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
                        "mintA": {"address": module.WRTC_MINT},
                        "mintB": {"address": module.WSOL_MINT},
                        "price": 0.00126628405540796,
                        "tvl": 778.37,
                        "day": {"volume": 12.5},
                    }
                ],
            },
        }
    )

    assert pool["pool_id"] == "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"
    assert pool["price_sol"] == 0.00126628405540796
    assert pool["liquidity"] == 778.37
    assert pool["volume_24h"] == 12.5
    assert pool["url"].startswith("https://raydium.io/swap/")


def test_parse_raydium_pool_info_ignores_unmatched_pool_rows(monkeypatch):
    module = load_bot_module(monkeypatch)

    pool = module.parse_raydium_pool_info(
        {
            "success": True,
            "data": {
                "data": [
                    {
                        "id": "unrelated-pool",
                        "mintA": {"address": module.WSOL_MINT},
                        "mintB": {"address": "other-token"},
                        "price": 99,
                        "tvl": 999999,
                        "day": {"volume": 999999},
                    }
                ],
            },
        }
    )

    assert pool == {
        "price_sol": None,
        "liquidity": 0.0,
        "volume_24h": 0.0,
        "pool_id": "",
        "url": module.RAYDIUM_SWAP_URL,
    }


def test_parse_raydium_pool_info_inverts_when_wrtc_is_quote_mint(monkeypatch):
    module = load_bot_module(monkeypatch)

    pool = module.parse_raydium_pool_info(
        {
            "success": True,
            "data": {
                "data": [
                    {
                        "mintA": {"address": module.WSOL_MINT},
                        "mintB": {"address": module.WRTC_MINT},
                        "price": 800.0,
                        "tvl": "1000.5",
                        "day": {"volume": "20.25"},
                    }
                ],
            },
        }
    )

    assert pool["price_sol"] == 0.00125
    assert pool["liquidity"] == 1000.5
    assert pool["volume_24h"] == 20.25


def test_fetch_price_data_uses_raydium_endpoints(monkeypatch):
    module = load_bot_module(monkeypatch)
    calls = []

    async def fake_get_json(url, params=None, *, verify_ssl=True):
        calls.append((url, params, verify_ssl))
        if url == module.RAYDIUM_MINT_PRICE_URL:
            return {"success": True, "data": {module.WRTC_MINT: "0.102"}}
        if url == module.RAYDIUM_POOL_INFO_URL:
            return {
                "success": True,
                "data": {
                    "data": [
                        {
                            "id": "pool-1",
                            "mintA": {"address": module.WRTC_MINT},
                            "mintB": {"address": module.WSOL_MINT},
                            "price": "0.0012",
                            "tvl": "900",
                            "day": {"volume": "7.5"},
                        }
                    ],
                },
            }
        raise AssertionError(url)

    monkeypatch.setattr(module, "_get_json", fake_get_json)

    price = asyncio.run(module.fetch_price_data())

    assert price == {
        "price_usd": 0.102,
        "price_sol": 0.0012,
        "liquidity": 900.0,
        "volume_24h": 7.5,
        "pool_id": "pool-1",
        "url": module.RAYDIUM_SWAP_URL,
    }
    assert calls[0] == (
        module.RAYDIUM_MINT_PRICE_URL,
        {"mints": module.WRTC_MINT},
        True,
    )
    assert calls[1][0] == module.RAYDIUM_POOL_INFO_URL
    assert calls[1][1]["mint1"] == module.WRTC_MINT
    assert calls[1][1]["mint2"] == module.WSOL_MINT
