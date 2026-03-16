"""Tests for monitor alert detection logic."""

from __future__ import annotations

import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rustchain_alerts.api import MinerInfo, WalletBalance
from rustchain_alerts.config import AppConfig, AlertThresholds
from rustchain_alerts.db import AlertDB
from rustchain_alerts.monitor import MinerMonitor


@pytest.fixture
def config(tmp_path):
    cfg = AppConfig()
    cfg.db_path = str(tmp_path / "test.db")
    cfg.thresholds.offline_minutes = 10
    cfg.thresholds.large_transfer_rtc = 10.0
    cfg.thresholds.reward_min_rtc = 0.01
    return cfg


@pytest.fixture
def monitor(config):
    mon = MinerMonitor(config)
    return mon


def make_miner(miner_id: str, last_attest: Optional[int] = None) -> MinerInfo:
    return MinerInfo(
        miner=miner_id,
        last_attest=last_attest or int(time.time()),
        entropy_score=0.5,
        device_arch="x86",
        device_family="x86_64",
        hardware_type="x86-64 (Modern)",
    )


# ── offline detection ─────────────────────────────────────────────────────────

def test_no_alert_when_recently_active(monitor):
    now = int(time.time())
    miner = make_miner("miner-1", last_attest=now - 60)  # 1 min ago
    events = monitor._check_offline(miner, now, prev=None)
    assert events == []


def test_offline_alert_when_stale(monitor):
    now = int(time.time())
    miner = make_miner("miner-1", last_attest=now - 900)  # 15 min ago, threshold=10
    events = monitor._check_offline(miner, now, prev=None)
    assert len(events) == 1
    assert events[0].alert_type == "offline"


def test_no_duplicate_offline_alert(monitor):
    now = int(time.time())
    miner = make_miner("miner-1", last_attest=now - 900)
    # first fire
    events1 = monitor._check_offline(miner, now, prev=None)
    assert len(events1) == 1
    # second call — was_alerted_recently should suppress
    events2 = monitor._check_offline(miner, now, prev={"offline_alerted": 0, "last_attest": miner.last_attest})
    assert events2 == []


def test_back_online_clears_flag(monitor):
    now = int(time.time())
    miner = make_miner("miner-1", last_attest=now - 30)  # recent
    prev = {"offline_alerted": 1, "last_attest": now - 30}
    events = monitor._check_offline(miner, now, prev)
    assert len(events) == 1
    assert events[0].alert_type == "back_online"


# ── balance change detection ──────────────────────────────────────────────────

def test_reward_alert_on_balance_increase(monitor):
    events = monitor._check_balance_changes("miner-1", prev_balance=5.0, curr_balance=5.5)
    assert len(events) == 1
    assert events[0].alert_type == "reward"
    assert "+0.5" in events[0].message


def test_no_reward_alert_below_threshold(monitor):
    events = monitor._check_balance_changes("miner-1", prev_balance=5.0, curr_balance=5.005)
    assert events == []


def test_large_transfer_alert(monitor):
    events = monitor._check_balance_changes("miner-1", prev_balance=100.0, curr_balance=85.0)
    assert len(events) == 1
    assert events[0].alert_type == "large_transfer"


def test_no_large_transfer_alert_below_threshold(monitor):
    events = monitor._check_balance_changes("miner-1", prev_balance=100.0, curr_balance=95.0)
    assert events == []


# ── attestation failure ───────────────────────────────────────────────────────

def test_attest_fail_when_timestamp_unchanged(monitor):
    miner = make_miner("miner-1", last_attest=1000)
    prev = {"last_attest": 1000, "balance_rtc": 5.0, "offline_alerted": 0}
    events = monitor._check_attest_fail(miner, prev)
    assert len(events) == 1
    assert events[0].alert_type == "attest_fail"


def test_no_attest_fail_when_timestamp_changed(monitor):
    miner = make_miner("miner-1", last_attest=2000)
    prev = {"last_attest": 1000, "balance_rtc": 5.0, "offline_alerted": 0}
    events = monitor._check_attest_fail(miner, prev)
    assert events == []


def test_no_attest_fail_on_first_poll(monitor):
    miner = make_miner("miner-1", last_attest=1000)
    events = monitor._check_attest_fail(miner, prev=None)
    assert events == []


# ── config ────────────────────────────────────────────────────────────────────

def test_watch_all_resolves_to_all_miners(monitor):
    monitor.config.miners.watch_all = True
    miners = [make_miner("a"), make_miner("b"), make_miner("c")]
    ids = monitor._resolve_watch_ids(miners)
    assert ids == {"a", "b", "c"}


def test_watch_ids_filters_miners(monitor):
    monitor.config.miners.watch_all = False
    monitor.config.miners.watch_ids = ["a", "c"]
    miners = [make_miner("a"), make_miner("b"), make_miner("c")]
    ids = monitor._resolve_watch_ids(miners)
    assert ids == {"a", "c"}
