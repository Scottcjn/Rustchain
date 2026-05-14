# SPDX-License-Identifier: MIT

import pytest

from tools import discord_leaderboard_bot as bot


def test_leaderboard_formatting_truncates_and_ranks_rows():
    rows = [
        {"miner": "miner-address-with-a-long-suffix", "balance_rtc": 12.3456789, "arch": "POWER8"},
        {"miner": "short", "balance_rtc": 1.0, "arch": "G4"},
    ]

    table = bot.build_leaderboard_lines(rows, top_n=1)

    assert "Rank  Miner" in table
    assert "   1  miner-address-wi...     12.345679  POWER8" in table
    assert "short" not in table
    assert bot.short_id("abc", keep=5) == "abc"
    assert bot.short_id("abcdef", keep=5) == "abcde..."
    assert bot.fmt_rtc(1.2) == "1.200000"


def test_architecture_distribution_normalizes_missing_values():
    dist = bot.architecture_distribution(
        [
            {"arch": "POWER8"},
            {"arch": " "},
            {"arch": None},
            {},
        ]
    )

    assert dist == [("unknown", 3, 75.0), ("POWER8", 1, 25.0)]
    assert bot.architecture_distribution([]) == []


def test_rewards_for_epoch_sorts_rewards_and_handles_fetch_errors(monkeypatch):
    def fake_get_json(session, url, timeout):
        assert url == "https://node.example/rewards/epoch/7"
        return {
            "rewards": [
                {"miner_id": "miner-low", "share_rtc": "1.5"},
                {"miner_id": "miner-high", "share_rtc": "3.25"},
                {"share_rtc": 0.5},
            ]
        }

    monkeypatch.setattr(bot, "get_json", fake_get_json)

    rewards = bot.rewards_for_epoch(object(), "https://node.example", 7, timeout=2.0)

    assert rewards == [
        {"miner": "miner-high", "share_rtc": 3.25},
        {"miner": "miner-low", "share_rtc": 1.5},
        {"miner": "unknown", "share_rtc": 0.5},
    ]

    monkeypatch.setattr(bot, "get_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    assert bot.rewards_for_epoch(object(), "https://node.example", 7, timeout=2.0) == []


def test_collect_data_filters_missing_miners_and_tolerates_balance_errors(monkeypatch):
    responses = {
        "https://node.example/api/miners": [
            {"miner": "miner-a", "device_arch": "POWER8", "antiquity_multiplier": "2.5"},
            {"miner_id": "miner-b", "device_family": "G5"},
            {"device_arch": "ignored"},
        ],
        "https://node.example/epoch": {"epoch": 5},
        "https://node.example/health": {"ok": True},
        "https://node.example/wallet/balance?miner_id=miner-a": {"amount_rtc": "9.5"},
    }

    def fake_get_json(session, url, timeout):
        if url == "https://node.example/wallet/balance?miner_id=miner-b":
            raise RuntimeError("balance unavailable")
        return responses[url]

    monkeypatch.setattr(bot, "get_json", fake_get_json)

    rows, epoch, health = bot.collect_data(object(), "https://node.example", timeout=1.0)

    assert epoch == {"epoch": 5}
    assert health == {"ok": True}
    assert rows == [
        {"miner": "miner-a", "balance_rtc": 9.5, "arch": "POWER8", "multiplier": 2.5},
        {"miner": "miner-b", "balance_rtc": 0.0, "arch": "G5", "multiplier": 0.0},
    ]


def test_render_payload_includes_top_table_and_reward_fallback(monkeypatch):
    monkeypatch.setattr(bot, "rewards_for_epoch", lambda *args, **kwargs: [])

    payload = bot.render_payload(
        object(),
        "https://node.example",
        1.0,
        rows=[{"miner": "miner-a", "balance_rtc": 2.0, "arch": "G4"}],
        epoch={"epoch": 3},
        health={"ok": True, "uptime_s": 42},
        top_n=5,
        title_prefix="Daily RustChain",
    )

    assert payload["content"].startswith("Daily RustChain\nEpoch: 3")
    assert "Total RTC across miners: 2.000000" in payload["content"]
    assert payload["embeds"][0]["fields"][1]["value"] == "No reward rows available for current epoch."
    assert "miner-a" in payload["embeds"][0]["fields"][0]["value"]
