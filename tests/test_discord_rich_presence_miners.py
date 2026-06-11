# SPDX-License-Identifier: MIT
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "discord_rich_presence.py"


def load_module():
    fake_pypresence = types.ModuleType("pypresence")
    fake_pypresence.Presence = object
    sys.modules.setdefault("pypresence", fake_pypresence)
    spec = importlib.util.spec_from_file_location("discord_rich_presence", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_normalize_miners_payload_accepts_current_envelope_and_legacy_list():
    mod = load_module()
    rows = [{"miner": "alice"}, {"miner_id": "bob"}, "bad-row"]

    assert mod.normalize_miners_payload({"miners": rows, "pagination": {"total": 2}}) == rows[:2]
    assert mod.normalize_miners_payload(rows) == rows[:2]
    assert mod.normalize_miners_payload({"pagination": {"total": 0}}) == []


def test_get_miners_list_unwraps_paginated_api_payload(monkeypatch):
    mod = load_module()

    def fake_get(url, verify, timeout):
        assert url == "https://rustchain.org/api/miners"
        assert timeout == 10
        return FakeResponse(
            {
                "miners": [
                    {"miner_id": "wallet-1", "hardware_type": "PowerPC G4"},
                    {"name": "wallet-2", "hardware_type": "x86-64"},
                ],
                "pagination": {"total": 2, "limit": 100, "offset": 0},
            }
        )

    monkeypatch.setattr(mod.requests, "get", fake_get)

    assert mod.get_miners_list() == [
        {"miner_id": "wallet-1", "hardware_type": "PowerPC G4"},
        {"name": "wallet-2", "hardware_type": "x86-64"},
    ]
    assert mod.miner_identifier(mod.get_miners_list()[0]) == "wallet-1"

