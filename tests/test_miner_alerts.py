# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def miner_alerts_module(monkeypatch):
    fake_dotenv = types.SimpleNamespace(load_dotenv=lambda: None)
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "miner_alerts"
        / "miner_alerts.py"
    )
    spec = importlib.util.spec_from_file_location("miner_alerts", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_alert_db_subscription_lifecycle_and_filters(
    miner_alerts_module,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(miner_alerts_module.time, "time", lambda: 1_700_000_000)
    db = miner_alerts_module.AlertDB(str(tmp_path / "alerts.db"))
    try:
        with pytest.raises(ValueError, match="At least one"):
            db.add_subscription("miner-a")

        sub_id = db.add_subscription(
            "miner-a",
            email="alice@example.com",
            phone="+15550001",
            alerts={"alert_rewards": 0},
        )

        assert isinstance(sub_id, int)
        all_subs = db.get_subscriptions("miner-a")
        assert len(all_subs) == 1
        assert all_subs[0]["email"] == "alice@example.com"
        assert all_subs[0]["phone"] == "+15550001"
        assert all_subs[0]["alert_offline"] == 1
        assert all_subs[0]["alert_rewards"] == 0
        assert db.get_subscriptions("miner-a", "offline")
        assert db.get_subscriptions("miner-a", "rewards") == []

        db.add_subscription(
            "miner-a",
            email="alice@example.com",
            phone="+15550002",
            alerts={"alert_rewards": 1},
        )
        updated = db.get_subscriptions("miner-a")[0]
        assert updated["phone"] == "+15550002"
        assert updated["alert_rewards"] == 1

        assert len(db.list_subscriptions()) == 1
        assert db.remove_subscription("miner-a", "alice@example.com") is True
        assert db.remove_subscription("miner-a", "alice@example.com") is True
        assert db.remove_subscription("miner-a", "missing@example.com") is False
        assert db.list_subscriptions() == []
    finally:
        db.close()


def test_alert_db_updates_state_and_recent_alerts(
    miner_alerts_module,
    tmp_path,
    monkeypatch,
):
    times = iter([1000, 1001, 1002, 1003, 1004, 5000])
    monkeypatch.setattr(miner_alerts_module.time, "time", lambda: next(times))
    db = miner_alerts_module.AlertDB(str(tmp_path / "alerts.db"))
    try:
        db.update_miner_state("miner-a", last_attest=900, balance_rtc=1.5, is_online=1)
        state = db.get_miner_state("miner-a")
        assert state["last_attest"] == 900
        assert state["balance_rtc"] == 1.5
        assert state["is_online"] == 1

        db.update_miner_state("miner-a", balance_rtc=3.0, is_online=0)
        state = db.get_miner_state("miner-a")
        assert state["balance_rtc"] == 3.0
        assert state["last_balance_change"] == 1.5
        assert state["is_online"] == 0

        assert db.recent_alert_exists("miner-a", "offline", cooldown_s=3600) is False
        db.log_alert(
            "miner-a",
            "offline",
            "offline",
            "email",
            "alice@example.com",
            success=True,
        )
        assert db.recent_alert_exists("miner-a", "offline", cooldown_s=3600) is True
        assert db.recent_alert_exists("miner-a", "offline", cooldown_s=10) is False
    finally:
        db.close()


def test_send_alert_delivers_enabled_channels_and_logs_history(
    miner_alerts_module,
    tmp_path,
    monkeypatch,
):
    db = miner_alerts_module.AlertDB(str(tmp_path / "alerts.db"))
    sent_email = []
    sent_sms = []
    try:
        db.add_subscription(
            "miner-a",
            email="alice@example.com",
            phone="+15550001",
        )
        db.add_subscription(
            "miner-a",
            email="disabled@example.com",
            alerts={"alert_offline": 0},
        )

        monkeypatch.setattr(
            miner_alerts_module,
            "send_email",
            lambda email, subject, html, text: sent_email.append(
                (email, subject, html, text)
            )
            or True,
        )
        monkeypatch.setattr(
            miner_alerts_module,
            "send_sms",
            lambda phone, message: sent_sms.append((phone, message)) or False,
        )
        monkeypatch.setattr(miner_alerts_module.time, "time", lambda: 1_700_000_000)

        miner_alerts_module.send_alert(
            db,
            "miner-a",
            "offline",
            "Subject",
            "<p>Body</p>",
            "Miner is offline",
        )

        assert sent_email == [
            ("alice@example.com", "Subject", "<p>Body</p>", "Miner is offline")
        ]
        assert sent_sms == [("+15550001", "[RustChain] Miner is offline")]

        rows = db.conn.execute(
            "SELECT channel, recipient, success FROM alert_history ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("email", "alice@example.com", 1),
            ("sms", "+15550001", 0),
        ]
    finally:
        db.close()


def test_alert_templates_respect_cooldowns_and_format_messages(
    miner_alerts_module,
    tmp_path,
    monkeypatch,
):
    db = miner_alerts_module.AlertDB(str(tmp_path / "alerts.db"))
    sent = []
    try:
        monkeypatch.setattr(miner_alerts_module.time, "time", lambda: 1_700_000_600)
        monkeypatch.setattr(
            miner_alerts_module,
            "send_alert",
            lambda *args: sent.append(args),
        )

        miner_alerts_module.alert_offline(db, "miner-a", 1_700_000_000)
        assert len(sent) == 1
        assert sent[0][2] == "offline"
        assert "Miner Offline" in sent[0][4]
        assert "10 min ago" in sent[0][5]

        db.log_alert("miner-a", "offline", "already sent", "email", "a@example.com")
        miner_alerts_module.alert_offline(db, "miner-a", 1_700_000_000)
        assert len(sent) == 1

        miner_alerts_module.alert_rewards(db, "miner-a", 1.23456, 9.87654)
        assert len(sent) == 2
        assert sent[1][2] == "rewards"
        assert "+1.2346 RTC" in sent[1][3]
        assert "9.8765 RTC" in sent[1][5]

        miner_alerts_module.alert_large_transfer(db, "miner-a", -12.5, 4.0)
        assert len(sent) == 3
        assert sent[2][2] == "large_transfer"
        assert "Large Transfer" in sent[2][3]
        assert "12.5000 RTC" in sent[2][5]

        miner_alerts_module.alert_attestation_fail(db, "miner-a", "missing")
        assert len(sent) == 4
        assert sent[3][2] == "attestation_fail"
        assert "missing" in sent[3][5]

        miner_alerts_module.alert_back_online(db, "miner-a")
        assert len(sent) == 5
        assert sent[4][2] == "offline"
        assert "back ONLINE" in sent[4][5]
    finally:
        db.close()


def test_fetch_helpers_parse_success_and_errors(miner_alerts_module, monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload, status_code=200, error=None):
            self.payload = payload
            self.status_code = status_code
            self.error = error

        def raise_for_status(self):
            if self.error:
                raise self.error

        def json(self):
            return self.payload

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/miners"):
            return FakeResponse([{"miner": "miner-a"}])
        return FakeResponse({"balance_rtc": "3.5"})

    monkeypatch.setattr(miner_alerts_module, "RUSTCHAIN_API", "https://node.example")
    monkeypatch.setattr(miner_alerts_module, "VERIFY_SSL", True)
    monkeypatch.setattr(miner_alerts_module.requests, "get", fake_get)

    assert miner_alerts_module.fetch_miners() == [{"miner": "miner-a"}]
    assert miner_alerts_module.fetch_balance("miner-a") == 3.5
    assert calls == [
        ("https://node.example/api/miners", {"verify": True, "timeout": 15}),
        (
            "https://node.example/balance",
            {"params": {"miner_id": "miner-a"}, "verify": True, "timeout": 10},
        ),
    ]

    monkeypatch.setattr(
        miner_alerts_module.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse({}, status_code=404),
    )
    assert miner_alerts_module.fetch_balance("missing") is None

    monkeypatch.setattr(
        miner_alerts_module.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse({"miners": []}),
    )
    assert miner_alerts_module.fetch_miners() == []

    monkeypatch.setattr(
        miner_alerts_module.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert miner_alerts_module.fetch_miners() == []
    assert miner_alerts_module.fetch_balance("miner-a") is None
