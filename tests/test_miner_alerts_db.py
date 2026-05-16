# SPDX-License-Identifier: MIT
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "miner_alerts"
    / "miner_alerts.py"
)
sys.modules.setdefault("dotenv", SimpleNamespace(load_dotenv=lambda *args, **kwargs: None))
spec = importlib.util.spec_from_file_location("miner_alerts", MODULE_PATH)
miner_alerts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(miner_alerts)

AlertDB = miner_alerts.AlertDB


def test_add_subscription_requires_email_or_phone(tmp_path):
    db = AlertDB(str(tmp_path / "alerts.db"))
    try:
        with pytest.raises(ValueError, match="At least one"):
            db.add_subscription("miner-1")
    finally:
        db.close()


def test_add_subscription_upserts_and_filters_by_alert_type(tmp_path):
    db = AlertDB(str(tmp_path / "alerts.db"))
    try:
        db.add_subscription(
            "miner-1",
            email="miner@example.com",
            phone="+15550001111",
            alerts={"alert_rewards": 0},
        )
        db.add_subscription(
            "miner-1",
            email="miner@example.com",
            phone="+15552223333",
            alerts={"alert_rewards": 1},
        )

        all_subs = db.get_subscriptions("miner-1")
        reward_subs = db.get_subscriptions("miner-1", "rewards")

        assert len(all_subs) == 1
        assert all_subs[0]["phone"] == "+15552223333"
        assert len(reward_subs) == 1
        assert reward_subs[0]["email"] == "miner@example.com"
    finally:
        db.close()


def test_remove_subscription_deactivates_without_deleting(tmp_path):
    db = AlertDB(str(tmp_path / "alerts.db"))
    try:
        db.add_subscription("miner-1", email="miner@example.com")

        assert db.remove_subscription("miner-1", "miner@example.com") is True
        assert db.get_subscriptions("miner-1") == []
        assert db.remove_subscription("miner-1", "missing@example.com") is False
    finally:
        db.close()


def test_update_miner_state_inserts_then_tracks_balance_change(tmp_path, monkeypatch):
    db = AlertDB(str(tmp_path / "alerts.db"))
    monkeypatch.setattr(miner_alerts.time, "time", lambda: 1_700_000_000)
    try:
        db.update_miner_state("miner-1", last_attest=100, balance_rtc=1.5, is_online=1)
        first = db.get_miner_state("miner-1")
        assert first["last_attest"] == 100
        assert first["balance_rtc"] == 1.5
        assert first["last_checked"] == 1_700_000_000

        monkeypatch.setattr(miner_alerts.time, "time", lambda: 1_700_000_060)
        db.update_miner_state("miner-1", balance_rtc=2.25, is_online=0)
        updated = db.get_miner_state("miner-1")

        assert updated["last_attest"] == 100
        assert updated["balance_rtc"] == 2.25
        assert updated["last_balance_change"] == pytest.approx(0.75)
        assert updated["is_online"] == 0
        assert updated["last_checked"] == 1_700_000_060
    finally:
        db.close()


def test_recent_alert_exists_honors_success_and_cooldown(tmp_path, monkeypatch):
    db = AlertDB(str(tmp_path / "alerts.db"))
    monkeypatch.setattr(miner_alerts.time, "time", lambda: 2_000)
    try:
        db.log_alert("miner-1", "offline", "old fail", "email", "a@example.com", False)
        assert db.recent_alert_exists("miner-1", "offline", cooldown_s=100) is False

        db.log_alert("miner-1", "offline", "recent success", "email", "a@example.com", True)
        assert db.recent_alert_exists("miner-1", "offline", cooldown_s=100) is True

        monkeypatch.setattr(miner_alerts.time, "time", lambda: 2_500)
        assert db.recent_alert_exists("miner-1", "offline", cooldown_s=100) is False
    finally:
        db.close()
