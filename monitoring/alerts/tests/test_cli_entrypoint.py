"""Tests for the rustchain_alerts CLI entry point."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from rustchain_alerts import __main__ as cli


def test_parse_args_accepts_custom_config_and_once(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["rustchain_alerts", "--config", "custom.yaml", "--once", "--log-level", "DEBUG"],
    )

    args = cli.parse_args()

    assert args.config == "custom.yaml"
    assert args.once is True
    assert args.history is False
    assert args.log_level == "DEBUG"


def test_main_runs_single_poll_and_closes_monitor(monkeypatch):
    config = SimpleNamespace(name="config")
    monitor = SimpleNamespace(_poll=AsyncMock(), run=AsyncMock(), aclose=AsyncMock())
    monitor_factory = Mock(return_value=monitor)
    monkeypatch.setattr(sys, "argv", ["rustchain_alerts", "--once"])
    monkeypatch.setattr(cli, "load_config", Mock(return_value=config))
    monkeypatch.setattr(cli, "MinerMonitor", monitor_factory)

    asyncio.run(cli.main())

    cli.load_config.assert_called_once_with("config.yaml")
    monitor_factory.assert_called_once_with(config)
    monitor._poll.assert_awaited_once_with()
    monitor.run.assert_not_called()
    monitor.aclose.assert_awaited_once_with()


def test_main_prints_history_without_polling(monkeypatch, capsys):
    config = SimpleNamespace(name="config")
    monitor = SimpleNamespace(
        db=SimpleNamespace(
            recent_alerts=Mock(return_value=[
                {
                    "fired_at": 1_700_000_000,
                    "miner_id": "miner-" + ("a" * 60),
                    "alert_type": "offline",
                    "message": "miner stopped attesting",
                }
            ])
        ),
        _poll=AsyncMock(),
        run=AsyncMock(),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(sys, "argv", ["rustchain_alerts", "--history"])
    monkeypatch.setattr(cli, "load_config", Mock(return_value=config))
    monkeypatch.setattr(cli, "MinerMonitor", Mock(return_value=monitor))

    asyncio.run(cli.main())

    output = capsys.readouterr().out
    assert "Miner" in output
    assert "offline" in output
    assert "miner stopped attesting" in output
    monitor.db.recent_alerts.assert_called_once_with(limit=50)
    monitor._poll.assert_not_called()
    monitor.run.assert_not_called()
    monitor.aclose.assert_not_called()
