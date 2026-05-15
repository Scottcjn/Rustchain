# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "discord_leaderboard_bot.py"
spec = importlib.util.spec_from_file_location("discord_leaderboard_bot", MODULE_PATH)
discord_leaderboard_bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discord_leaderboard_bot)


def test_formatting_helpers_truncate_ids_and_format_rtc():
    assert discord_leaderboard_bot.fmt_rtc(1.2) == "1.200000"
    assert discord_leaderboard_bot.short_id("short", keep=10) == "short"
    assert discord_leaderboard_bot.short_id("miner-abcdefghijklmnopqrstuvwxyz", keep=12) == "miner-abcdef..."


def test_build_leaderboard_lines_limits_rows_and_uses_unknown_arch():
    rows = [
        {"miner": "miner-one-long-id", "balance_rtc": 5.5, "arch": "G5"},
        {"miner": "miner-two", "balance_rtc": 1.25},
    ]

    table = discord_leaderboard_bot.build_leaderboard_lines(rows, top_n=1)

    assert "Rank  Miner" in table
    assert "miner-one-long-i..." in table
    assert "5.500000" in table
    assert "miner-two" not in table


def test_architecture_distribution_counts_blank_as_unknown():
    rows = [{"arch": "G5"}, {"arch": ""}, {"arch": None}, {"arch": "G5"}]

    dist = discord_leaderboard_bot.architecture_distribution(rows)

    assert dist[0] == ("G5", 2, 50.0)
    assert dist[1] == ("unknown", 2, 50.0)


def test_rewards_for_epoch_sorts_rewards_and_returns_empty_on_fetch_failure(monkeypatch):
    def fake_get_json(session, url, timeout):
        return {
            "rewards": [
                {"miner_id": "small", "share_rtc": "1.5"},
                {"miner_id": "large", "share_rtc": "3.25"},
            ]
        }

    monkeypatch.setattr(discord_leaderboard_bot, "get_json", fake_get_json)
    rewards = discord_leaderboard_bot.rewards_for_epoch(object(), "https://node", 7, 1)
    assert rewards == [
        {"miner": "large", "share_rtc": 3.25},
        {"miner": "small", "share_rtc": 1.5},
    ]

    monkeypatch.setattr(
        discord_leaderboard_bot,
        "get_json",
        lambda session, url, timeout: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert discord_leaderboard_bot.rewards_for_epoch(object(), "https://node", 7, 1) == []


def test_render_payload_includes_top_miners_rewards_and_architecture(monkeypatch):
    monkeypatch.setattr(
        discord_leaderboard_bot,
        "rewards_for_epoch",
        lambda session, base, epoch, timeout: [{"miner": "winner-miner-id", "share_rtc": 2}],
    )
    rows = [
        {"miner": "alice-miner", "balance_rtc": 4.0, "arch": "G4"},
        {"miner": "bob-miner", "balance_rtc": 2.0, "arch": "G5"},
    ]

    payload = discord_leaderboard_bot.render_payload(
        object(),
        "https://node",
        1,
        rows,
        {"epoch": 12},
        {"ok": True, "uptime_s": 99},
        top_n=2,
        title_prefix="Daily leaderboard",
    )

    assert "Daily leaderboard" in payload["content"]
    assert "Epoch: 12" in payload["content"]
    fields = {field["name"]: field["value"] for field in payload["embeds"][0]["fields"]}
    assert "alice-miner" in fields["Top Miners"]
    assert "winner-miner-id" in fields["Top Earners (current epoch)"]
    assert "- G4: 1 (50.0%)" in fields["Architecture Distribution"]


def test_render_payload_handles_missing_rewards_and_empty_distribution(monkeypatch):
    monkeypatch.setattr(
        discord_leaderboard_bot,
        "rewards_for_epoch",
        lambda session, base, epoch, timeout: [],
    )

    payload = discord_leaderboard_bot.render_payload(
        object(),
        "https://node",
        1,
        [],
        {"epoch": -1},
        {"ok": False, "uptime_s": 0},
        top_n=5,
        title_prefix="Daily leaderboard",
    )

    assert "Epoch: -1" in payload["content"]
    fields = {field["name"]: field["value"] for field in payload["embeds"][0]["fields"]}
    assert fields["Top Miners"].startswith("```text\nRank  Miner")
    assert fields["Top Earners (current epoch)"] == "No reward rows available for current epoch."
    assert fields["Architecture Distribution"] == "No data"


def test_collect_data_skips_rows_without_miner_and_fetches_wallet_balances(monkeypatch):
    calls = []

    def fake_get_json(session, url, timeout):
        calls.append(url)
        if url.endswith("/api/miners"):
            return [
                {"miner": "miner-b", "device_family": "x86", "antiquity_multiplier": 1.25},
                {"device_arch": "ARM"},
                {"miner_id": "miner-a", "device_arch": "ARM64", "antiquity_multiplier": 2},
            ]
        if url.endswith("/epoch"):
            return {"epoch": 99}
        if url.endswith("/health"):
            return {"ok": True, "uptime_s": 321}
        if "miner_id=miner-b" in url:
            return {"amount_rtc": "3.5"}
        if "miner_id=miner-a" in url:
            return {"amount_rtc": 7}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(discord_leaderboard_bot, "get_json", fake_get_json)

    rows, epoch, health = discord_leaderboard_bot.collect_data(object(), "https://node", 10)

    assert rows == [
        {"miner": "miner-a", "balance_rtc": 7.0, "arch": "ARM64", "multiplier": 2.0},
        {"miner": "miner-b", "balance_rtc": 3.5, "arch": "x86", "multiplier": 1.25},
    ]
    assert epoch == {"epoch": 99}
    assert health == {"ok": True, "uptime_s": 321}
    assert any(url.endswith("/api/miners") for url in calls)
    assert any("wallet/balance?miner_id=miner-a" in url for url in calls)
    assert any("wallet/balance?miner_id=miner-b" in url for url in calls)
