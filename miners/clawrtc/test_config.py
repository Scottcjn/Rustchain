"""Tests for clawrtc config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Allow importing from the same directory
import sys
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    ConfigError,
    get_config_path,
    get_default_config,
    load_config,
    save_config,
    validate_config,
)


@pytest.fixture
def tmp_config(tmp_path):
    """Provide a temporary config file path."""
    return str(tmp_path / "config.json")


@pytest.fixture
def sample_config():
    """Return a valid sample config."""
    cfg = get_default_config()
    cfg["wallet_address"] = "RTC1234567890abcdef"
    cfg["node_url"] = "https://rustchain.org"
    return cfg


# ── get_config_path ──────────────────────────────────────────────────────

class TestGetConfigPath:
    def test_default_path(self):
        path = get_config_path()
        assert path.parent.name == ".clawrtc"
        assert path.name == "config.json"

    def test_custom_path(self):
        path = get_config_path("/tmp/custom.json")
        assert path == Path("/tmp/custom.json")

    def test_tilde_expansion(self):
        path = get_config_path("~/myconfig.json")
        assert "~" not in str(path)


# ── get_default_config ───────────────────────────────────────────────────

class TestGetDefaultConfig:
    def test_returns_dict(self):
        cfg = get_default_config()
        assert isinstance(cfg, dict)

    def test_returns_copy(self):
        a = get_default_config()
        b = get_default_config()
        a["wallet_address"] = "MODIFIED"
        assert b["wallet_address"] == ""

    def test_has_required_keys(self):
        cfg = get_default_config()
        for key in ["wallet_address", "node_url", "mining_threads",
                     "poll_interval_seconds", "pow_chains", "log_level"]:
            assert key in cfg


# ── load_config ──────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_creates_default_when_missing(self, tmp_config):
        cfg = load_config(tmp_config)
        assert isinstance(cfg, dict)
        assert Path(tmp_config).exists()

    def test_loads_existing_config(self, tmp_config, sample_config):
        with open(tmp_config, "w") as f:
            json.dump(sample_config, f)
        cfg = load_config(tmp_config)
        assert cfg["wallet_address"] == "RTC1234567890abcdef"

    def test_merges_missing_keys(self, tmp_config):
        """Old configs missing new fields get defaults filled in."""
        with open(tmp_config, "w") as f:
            json.dump({"wallet_address": "RTCabc", "node_url": "https://example.com"}, f)
        cfg = load_config(tmp_config)
        assert "mining_threads" in cfg
        assert "log_level" in cfg
        assert cfg["wallet_address"] == "RTCabc"

    def test_rejects_invalid_json(self, tmp_config):
        with open(tmp_config, "w") as f:
            f.write("{bad json!!")
        with pytest.raises(ConfigError, match="Invalid JSON"):
            load_config(tmp_config)

    def test_rejects_non_object(self, tmp_config):
        with open(tmp_config, "w") as f:
            json.dump([1, 2, 3], f)
        with pytest.raises(ConfigError, match="JSON object"):
            load_config(tmp_config)

    def test_preserves_extra_keys(self, tmp_config):
        """User-added keys are kept (forward compat)."""
        with open(tmp_config, "w") as f:
            json.dump({"wallet_address": "RTCx", "custom_field": 42}, f)
        cfg = load_config(tmp_config)
        assert cfg["custom_field"] == 42


# ── save_config ──────────────────────────────────────────────────────────

class TestSaveConfig:
    def test_saves_valid_config(self, tmp_config, sample_config):
        path = save_config(sample_config, tmp_config)
        assert Path(path).exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["wallet_address"] == sample_config["wallet_address"]

    def test_creates_parent_dirs(self, tmp_path):
        deep = str(tmp_path / "a" / "b" / "config.json")
        cfg = get_default_config()
        save_config(cfg, deep)
        assert Path(deep).exists()

    def test_rejects_invalid_config(self, tmp_config):
        bad = {"mining_threads": "not_a_number"}
        with pytest.raises(ConfigError, match="Invalid configuration"):
            save_config(bad, tmp_config)

    def test_roundtrip(self, tmp_config, sample_config):
        save_config(sample_config, tmp_config)
        loaded = load_config(tmp_config)
        for key in sample_config:
            assert loaded[key] == sample_config[key]


# ── validate_config ─────────────────────────────────────────────────────

class TestValidateConfig:
    def test_valid_default(self):
        errors = validate_config(get_default_config())
        assert errors == []

    def test_wrong_type_threads(self):
        cfg = get_default_config()
        cfg["mining_threads"] = "four"
        errors = validate_config(cfg)
        assert any("mining_threads" in e for e in errors)

    def test_threads_too_low(self):
        cfg = get_default_config()
        cfg["mining_threads"] = 0
        errors = validate_config(cfg)
        assert any("mining_threads" in e for e in errors)

    def test_poll_too_low(self):
        cfg = get_default_config()
        cfg["poll_interval_seconds"] = 1
        errors = validate_config(cfg)
        assert any("poll_interval_seconds" in e for e in errors)

    def test_invalid_log_level(self):
        cfg = get_default_config()
        cfg["log_level"] = "VERBOSE"
        errors = validate_config(cfg)
        assert any("log_level" in e for e in errors)

    def test_pow_chains_bad_entry(self):
        cfg = get_default_config()
        cfg["pow_chains"] = ["ergo", 123]
        errors = validate_config(cfg)
        assert any("pow_chains" in e for e in errors)

    def test_non_dict_input(self):
        errors = validate_config("not a dict")
        assert len(errors) == 1

    def test_valid_full_config(self, sample_config):
        errors = validate_config(sample_config)
        assert errors == []

    def test_valid_log_levels(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            cfg = get_default_config()
            cfg["log_level"] = level
            assert validate_config(cfg) == []
