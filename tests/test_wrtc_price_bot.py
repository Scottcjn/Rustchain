# SPDX-License-Identifier: MIT
import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "wrtc-price-bot" / "bot.py"


def load_module(monkeypatch):
    telegram = types.ModuleType("telegram")
    telegram.Update = object

    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.ApplicationBuilder = object
    telegram_ext.CommandHandler = object
    telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    telegram_ext.JobQueue = object

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", telegram_ext)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)

    spec = importlib.util.spec_from_file_location("wrtc_price_bot", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_get_price_data_prefers_raydium_pair(monkeypatch):
    module = load_module(monkeypatch)
    payload = {
        "pairs": [
            {"dexId": "other", "priceUsd": "0.01"},
            {
                "dexId": "raydium",
                "priceUsd": "0.25",
                "priceNative": "0.002",
                "priceChange": {"h24": "12.5", "h1": "-1.25"},
                "liquidity": {"usd": "1500"},
                "volume": {"h24": "750"},
                "url": "https://dex.example/pair",
            },
        ]
    }

    monkeypatch.setattr(module.requests, "get", lambda url, timeout: Response(payload))

    data = module.get_price_data()

    assert data == {
        "price_usd": 0.25,
        "price_native": "0.002",
        "h24_change": 12.5,
        "h1_change": -1.25,
        "liquidity_usd": 1500.0,
        "volume_h24": 750.0,
        "url": "https://dex.example/pair",
    }


def test_get_price_data_ignores_malformed_pairs(monkeypatch):
    module = load_module(monkeypatch)
    payload = {
        "pairs": [
            ["bad"],
            {
                "dexId": "raydium",
                "priceUsd": "bad",
                "priceChange": "bad",
                "liquidity": None,
                "volume": [],
            },
        ]
    }

    monkeypatch.setattr(module.requests, "get", lambda url, timeout: Response(payload))

    data = module.get_price_data()

    assert data["price_usd"] == 0.0
    assert data["h24_change"] == 0.0
    assert data["h1_change"] == 0.0
    assert data["liquidity_usd"] == 0.0
    assert data["volume_h24"] == 0.0


def test_get_price_data_rejects_non_object_payload(monkeypatch):
    module = load_module(monkeypatch)

    monkeypatch.setattr(module.requests, "get", lambda url, timeout: Response([]))

    assert module.get_price_data() is None
