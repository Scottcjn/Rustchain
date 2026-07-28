# SPDX-License-Identifier: MIT
"""Regression test: DexScreener returns numeric fields as JSON *strings*.

fetch_dexscreener_price() must not blow up on them (and get_price() must not
silently fall through to the Jupiter fallback as a result).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "wrtc_price_bot" / "wrtc_price_bot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wrtc_price_bot_mod", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["wrtc_price_bot_mod"] = module
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


# Exactly the shape api.dexscreener.com returns: every numeric field is a string.
DEX_PAYLOAD = {
    "pairs": [
        {
            "priceUsd": "0.25",
            "priceNative": "0.002",
            "priceChange": {"h24": "12.5"},
            "liquidity": {"usd": "1500"},
        }
    ]
}


@pytest.fixture()
def module(monkeypatch):
    mod = load_module()
    monkeypatch.setattr(mod.requests, "get", lambda url, timeout: Response(DEX_PAYLOAD))
    return mod


def test_dexscreener_parses_string_fields(module):
    fetcher = module.PriceFetcher()
    data = fetcher.fetch_dexscreener_price()

    assert data is not None, "DexScreener parse returned None on a valid API payload"
    assert data["price_usd"] == 0.25
    assert data["price_sol"] == 0.002
    assert data["change_24h"] == 12.5
    assert data["liquidity"] == 1500.0
    # 0.25 USD per wRTC / 0.002 SOL per wRTC == 125 USD per SOL
    assert data["sol_price_usd"] == pytest.approx(125.0)


def test_get_price_uses_dexscreener_not_jupiter_fallback(module):
    fetcher = module.PriceFetcher()
    data = fetcher.get_price()

    assert data is not None
    # The real bug's user-visible symptom: source silently degrades to jupiter,
    # dropping 24h change / liquidity / SOL price to zero.
    assert data["source"] == "dexscreener"
    assert data["change_24h"] == 12.5
    assert data["liquidity"] == 1500.0
