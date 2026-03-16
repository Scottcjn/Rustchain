"""Tests for config loading."""

import os
import textwrap
from pathlib import Path

import pytest

from rustchain_alerts.config import load_config, AppConfig


def test_default_config_loads():
    cfg = load_config("nonexistent.yaml")
    assert cfg.rustchain.base_url == "https://50.28.86.131"
    assert cfg.thresholds.offline_minutes == 10
    assert cfg.email.enabled is False
    assert cfg.sms.enabled is False


def test_yaml_config_overrides_defaults(tmp_path):
    yaml_content = textwrap.dedent("""\
        rustchain:
          poll_interval_seconds: 30
        thresholds:
          offline_minutes: 5
          large_transfer_rtc: 50.0
        email:
          enabled: true
          to_addrs:
            - admin@example.com
    """)
    p = tmp_path / "config.yaml"
    p.write_text(yaml_content)

    cfg = load_config(p)
    assert cfg.rustchain.poll_interval_seconds == 30
    assert cfg.thresholds.offline_minutes == 5
    assert cfg.thresholds.large_transfer_rtc == 50.0
    assert cfg.email.enabled is True
    assert cfg.email.to_addrs == ["admin@example.com"]


def test_env_var_overrides_smtp_password(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "secret123")
    cfg = load_config("nonexistent.yaml")
    assert cfg.email.smtp_password == "secret123"


def test_env_var_overrides_twilio(tmp_path, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
    cfg = load_config("nonexistent.yaml")
    assert cfg.sms.account_sid == "ACtest"
    assert cfg.sms.auth_token == "token123"
