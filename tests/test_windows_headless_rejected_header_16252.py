# SPDX-License-Identifier: MIT
"""Regression tests for Issue #7368 / Bounty #16252 across both Windows miners:
- miners/windows/rustchain_windows_miner.py
- miners/windows/installer/src/rustchain_windows_miner.py
"""

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STANDALONE_MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"
INSTALLER_MINER_PATH = ROOT / "miners" / "windows" / "installer" / "src" / "rustchain_windows_miner.py"
SETUP_BAT_PATH = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"


def _load_miner_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.mark.parametrize(
    "miner_path,mod_name",
    [
        (STANDALONE_MINER_PATH, "standalone_windows_miner_16252"),
        (INSTALLER_MINER_PATH, "installer_windows_miner_16252"),
    ],
)
def test_terminal_rejection_stops_retry_and_surfaces_diagnostic(monkeypatch, miner_path, mod_name):
    module = _load_miner_module(miner_path, mod_name)
    monkeypatch.setattr(module.RustChainMiner, "_run_fingerprint_checks", lambda self: None, raising=False)
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    # Simulate real public node response from https://50.28.86.131/headers/ingest_signed
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_a, **_kw: _StubResponse(400, {"error": "message_header_mismatch", "ok": False}),
    )

    assert miner.submit_header({"header": {"slot": 27455}}) is False
    assert miner._last_submitted_slot == 27455
    assert miner.last_header_retryable is False
    assert miner._header_submission_due(27455, now=999999.0) is False
    assert "HTTP 400" in miner.last_header_error
    assert "message_header_mismatch" in miner.last_header_error

    line = module._format_headless_event({
        "type": "share",
        "slot": 27455,
        "submitted": 1,
        "accepted": 0,
        "success": False,
        "error": miner.last_header_error,
        "retryable": miner.last_header_retryable,
    })
    assert "slot=27455" in line
    assert "error=HTTP 400 error=message_header_mismatch" in line
    assert "class=terminal no_retry" in line


@pytest.mark.parametrize(
    "miner_path,mod_name",
    [
        (STANDALONE_MINER_PATH, "standalone_windows_miner_backoff_16252"),
        (INSTALLER_MINER_PATH, "installer_windows_miner_backoff_16252"),
    ],
)
def test_retryable_rejection_uses_bounded_exponential_backoff(monkeypatch, miner_path, mod_name):
    module = _load_miner_module(miner_path, mod_name)
    monkeypatch.setattr(module.RustChainMiner, "_run_fingerprint_checks", lambda self: None, raising=False)
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")
    monkeypatch.setattr(module.time, "monotonic", lambda: 200.0)
    monkeypatch.setattr(module.random, "uniform", lambda *_args: 1.0)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_a, **_kw: _StubResponse(503, {"ok": False, "error": "node restarting"}),
    )

    delays = []
    for _ in range(7):
        assert miner.submit_header({"header": {"slot": 27456}}) is False
        delays.append(miner.header_retry_in_seconds)

    assert delays == [10, 20, 40, 80, 160, 300, 300]
    assert miner._last_submitted_slot is None
    assert miner.last_header_retryable is True
    assert "HTTP 503" in miner.last_header_error
    assert "node restarting" in miner.last_header_error


def test_http_200_ok_false_respects_error_classification(monkeypatch):
    module = _load_miner_module(STANDALONE_MINER_PATH, "standalone_windows_miner_200_ok_false")
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")
    monkeypatch.setattr(module.time, "monotonic", lambda: 500.0)
    monkeypatch.setattr(module.random, "uniform", lambda *_args: 1.0)

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_a, **_kw: _StubResponse(200, {"ok": False, "error": "node restarting, try_again"}),
    )
    assert miner.submit_header({"header": {"slot": 27500}}) is False
    assert miner.last_header_retryable is True
    assert miner.header_retry_in_seconds == 10


def test_windows_bootstrap_hash_remains_in_sync():
    setup_text = SETUP_BAT_PATH.read_text(encoding="utf-8")
    match = re.search(r'set "MINER_SHA256=([0-9a-f]{64})"', setup_text, re.IGNORECASE)
    assert match is not None
    expected_sha = hashlib.sha256(STANDALONE_MINER_PATH.read_bytes()).hexdigest()
    assert match.group(1).lower() == expected_sha
