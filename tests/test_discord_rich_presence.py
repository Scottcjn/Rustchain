import importlib
import sys
import time
import types


class FakePresence:
    def __init__(self, client_id):
        self.client_id = client_id

    def connect(self):
        return None


sys.modules.setdefault(
    "pypresence",
    types.SimpleNamespace(Presence=FakePresence),
)

discord_rich_presence = importlib.import_module("discord_rich_presence")


def test_format_presence_data_defaults_missing_balance_and_epoch():
    presence = discord_rich_presence.format_presence_data(
        {},
        balance_data=None,
        epoch_data=None,
    )

    assert presence["details"] == "Balance: 0.00 RTC"
    assert presence["small_text"] == "E0 · S0"
    assert presence["balance"] == 0.0
    assert presence["uptime"] == "Unknown"
    assert "Unknown" in presence["state"]
    assert "1.0x" in presence["state"]


def test_format_presence_data_formats_full_online_miner_status():
    presence = discord_rich_presence.format_presence_data(
        {
            "hardware_type": "IBM POWER8 S824",
            "antiquity_multiplier": 2.5,
            "last_attest": time.time() - 60,
        },
        balance_data={"amount_rtc": 12.3456},
        epoch_data={"epoch": 7, "slot": 42},
    )

    assert presence["details"] == "Balance: 12.35 RTC"
    assert presence["small_text"] == "E7 · S42"
    assert presence["large_text"] == "IBM POWER8 S824 (2.5x reward)"
    assert presence["balance"] == 12.3456
    assert presence["uptime"] == "Online"
    assert "POWER8" in presence["state"]
    assert "2.5x" in presence["state"]
    assert "Online" in presence["state"]
