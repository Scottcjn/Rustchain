# SPDX-License-Identifier: MIT
import asyncio
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "discord-bot" / "bot.py"


def load_bot_module(monkeypatch):
    class FakeEmbed:
        def __init__(self, title=None, color=None, description=None):
            self.title = title
            self.color = color
            self.description = description
            self.fields = []
            self.footer = None
            self.timestamp = None

        def add_field(self, name, value, inline=True):
            self.fields.append({"name": name, "value": value, "inline": inline})

        def set_footer(self, text):
            self.footer = text

    class FakeColor:
        @staticmethod
        def green():
            return "green"

        @staticmethod
        def red():
            return "red"

        @staticmethod
        def blue():
            return "blue"

        @staticmethod
        def gold():
            return "gold"

        @staticmethod
        def purple():
            return "purple"

        @staticmethod
        def teal():
            return "teal"

    class FakeIntents:
        @classmethod
        def default(cls):
            return cls()

    class FakeTree:
        def command(self, **_kwargs):
            return lambda fn: fn

        async def sync(self):
            return None

    class FakeBot:
        def __init__(self, **_kwargs):
            self.tree = FakeTree()
            self.user = types.SimpleNamespace(id=1)

        async def close(self):
            return None

        def run(self, *_args, **_kwargs):
            return None

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            return None

        async def aclose(self):
            return None

    def describe(**_kwargs):
        return lambda fn: fn

    fake_app_commands = types.SimpleNamespace(describe=describe)
    fake_discord = types.SimpleNamespace(
        Embed=FakeEmbed,
        Color=FakeColor,
        Intents=FakeIntents,
        Interaction=object,
        app_commands=fake_app_commands,
    )
    fake_commands = types.SimpleNamespace(Bot=FakeBot)
    fake_ext = types.SimpleNamespace(commands=fake_commands)
    fake_httpx = types.SimpleNamespace(
        AsyncClient=FakeAsyncClient,
        Timeout=lambda timeout: timeout,
    )

    monkeypatch.setitem(sys.modules, "discord", fake_discord)
    monkeypatch.setitem(sys.modules, "discord.app_commands", fake_app_commands)
    monkeypatch.setitem(sys.modules, "discord.ext", fake_ext)
    monkeypatch.setitem(sys.modules, "discord.ext.commands", fake_commands)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))

    spec = importlib.util.spec_from_file_location("python_discord_bot", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_miners_command_uses_paginated_total_and_miner_id_fallback(monkeypatch):
    module = load_bot_module(monkeypatch)

    async def fake_miners():
        return {
            "miners": [
                {"miner_id": "alice-id", "device_arch": "G4", "device_family": "PowerPC"},
                {"miner": "bob", "antiquity_multiplier": 2.5},
            ],
            "pagination": {"total": 37, "limit": 2, "offset": 0, "count": 2},
        }

    module.bot.api = types.SimpleNamespace(miners=fake_miners)

    replies = []

    class FakeResponse:
        async def defer(self):
            return None

    class FakeFollowup:
        async def send(self, *args, **kwargs):
            replies.append((args, kwargs))

    interaction = types.SimpleNamespace(response=FakeResponse(), followup=FakeFollowup())

    asyncio.run(module.cmd_miners(interaction))

    assert len(replies) == 1
    embed = replies[0][1]["embed"]
    assert embed.title == "Active Miners (37)"
    assert embed.fields[0]["name"] == "alice-id"
    assert "Arch: G4" in embed.fields[0]["value"]
    assert embed.fields[1]["name"] == "bob"
    assert embed.footer == "Showing 2 of 37 miners | https://rustchain.org"
