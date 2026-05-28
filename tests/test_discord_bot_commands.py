# SPDX-License-Identifier: MIT
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "discord-bot" / "bot.py"


class FakeEmbed:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.fields = []
        self.timestamp = None
        self.footer = None

    def add_field(self, **kwargs):
        self.fields.append(kwargs)

    def set_footer(self, **kwargs):
        self.footer = kwargs


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


class FakeTree:
    def command(self, *_args, **_kwargs):
        return lambda func: func

    async def sync(self):
        return None


class FakeBot:
    def __init__(self, *_args, **_kwargs):
        self.tree = FakeTree()
        self.user = SimpleNamespace(id=123)

    async def close(self):
        return None


class FakeResponse:
    async def defer(self, **_kwargs):
        return None


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, *args, **kwargs):
        self.messages.append((args, kwargs))


def load_discord_bot_module():
    fake_app_commands = SimpleNamespace(describe=lambda **_kwargs: (lambda func: func))
    sys.modules["discord"] = SimpleNamespace(
        app_commands=fake_app_commands,
        Color=FakeColor,
        Embed=FakeEmbed,
        Intents=SimpleNamespace(default=lambda: SimpleNamespace(message_content=False)),
        Interaction=object,
    )
    sys.modules["discord.ext"] = SimpleNamespace(
        commands=SimpleNamespace(Bot=FakeBot)
    )
    sys.modules["discord.ext.commands"] = SimpleNamespace(Bot=FakeBot)
    sys.modules["discord.app_commands"] = fake_app_commands
    sys.modules["httpx"] = SimpleNamespace(
        AsyncClient=lambda *args, **kwargs: SimpleNamespace(aclose=lambda: None),
        Timeout=lambda *args, **kwargs: None,
    )

    spec = importlib.util.spec_from_file_location("rustchain_discord_bot", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rustchain_discord_bot"] = module
    spec.loader.exec_module(module)
    return module


def test_health_command_handles_null_uptime():
    module = load_discord_bot_module()

    class FakeApi:
        async def health(self):
            return {"ok": True, "version": "2.2.1", "uptime_s": None}

    followup = FakeFollowup()
    interaction = SimpleNamespace(response=FakeResponse(), followup=followup)
    module.bot.api = FakeApi()

    asyncio.run(module.cmd_health(interaction))

    embed = followup.messages[0][1]["embed"]
    fields = {field["name"]: field["value"] for field in embed.fields}
    assert fields["Uptime"] == "N/A"


def test_epoch_command_handles_null_numeric_fields():
    module = load_discord_bot_module()

    class FakeApi:
        async def epoch(self):
            return {
                "epoch": 42,
                "slot": None,
                "height": None,
                "blocks_per_epoch": None,
                "enrolled_miners": None,
                "epoch_pot": None,
            }

    followup = FakeFollowup()
    interaction = SimpleNamespace(response=FakeResponse(), followup=followup)
    module.bot.api = FakeApi()

    asyncio.run(module.cmd_epoch(interaction))

    embed = followup.messages[0][1]["embed"]
    fields = {field["name"]: field["value"] for field in embed.fields}
    assert fields["Slot"] == "N/A"
    assert fields["Height"] == "N/A"
    assert fields["Epoch Pot"] == "N/A"


def test_balance_command_handles_null_amount():
    module = load_discord_bot_module()

    class FakeApi:
        async def balance(self, miner_id):
            return {"miner_id": miner_id, "amount_rtc": None}

    followup = FakeFollowup()
    interaction = SimpleNamespace(response=FakeResponse(), followup=followup)
    module.bot.api = FakeApi()

    asyncio.run(module.cmd_balance(interaction, "alice-miner"))

    embed = followup.messages[0][1]["embed"]
    fields = {field["name"]: field["value"] for field in embed.fields}
    assert fields["Balance"] == "N/A"
