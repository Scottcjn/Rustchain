"""Configuration loader for RustChain alert system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel, Field


class RustChainConfig(BaseModel):
    base_url: str = "https://50.28.86.131"
    verify_ssl: bool = False
    poll_interval_seconds: int = 60


class AlertThresholds(BaseModel):
    offline_minutes: int = Field(default=10, description="Minutes without attestation before offline alert")
    large_transfer_rtc: float = Field(default=10.0, description="RTC balance drop threshold for large transfer alert")
    reward_min_rtc: float = Field(default=0.01, description="Minimum balance increase to trigger reward alert")


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)
    use_tls: bool = True


class SmsConfig(BaseModel):
    enabled: bool = False
    account_sid: str = ""
    auth_token: str = ""
    from_number: str = ""
    to_numbers: list[str] = Field(default_factory=list)


class MinersConfig(BaseModel):
    watch_all: bool = True
    watch_ids: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    rustchain: RustChainConfig = Field(default_factory=RustChainConfig)
    thresholds: AlertThresholds = Field(default_factory=AlertThresholds)
    email: EmailConfig = Field(default_factory=EmailConfig)
    sms: SmsConfig = Field(default_factory=SmsConfig)
    miners: MinersConfig = Field(default_factory=MinersConfig)
    db_path: str = "alerts.db"


def load_config(path: Union[str, Path] = "config.yaml") -> AppConfig:
    """Load config from YAML file, falling back to env vars for secrets."""
    p = Path(path)
    raw: dict = {}
    if p.exists():
        with p.open() as f:
            raw = yaml.safe_load(f) or {}

    config = AppConfig(**raw)

    # Allow env var overrides for secrets
    if smtp_pass := os.getenv("SMTP_PASSWORD"):
        config.email.smtp_password = smtp_pass
    if smtp_user := os.getenv("SMTP_USER"):
        config.email.smtp_user = smtp_user
    if twilio_token := os.getenv("TWILIO_AUTH_TOKEN"):
        config.sms.auth_token = twilio_token
    if twilio_sid := os.getenv("TWILIO_ACCOUNT_SID"):
        config.sms.account_sid = twilio_sid

    return config
