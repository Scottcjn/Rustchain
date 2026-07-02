# SPDX-License-Identifier: MIT
"""Regression tests for Issue #7368.

The Windows headless miner previously retried the same rejected signed
header every 10 seconds for the entire eligibility window because
``_last_submitted_slot`` was only updated on success. The
``_format_headless_event`` formatter also dropped the response
diagnostic, so operators running with ``--headless`` saw only ``FAIL``
and had to attach a debugger to learn the underlying HTTP reason.

These tests prove:

* ``submit_header`` records the slot as handled on both success and
  failure paths, so a rejected slot is not retried.
* The share event passed to the headless callback carries the safe
  ``last_header_error`` diagnostic when a submission fails.
* ``_format_headless_event`` includes both the slot and the diagnostic
  in the headless line.
"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _load_windows_miner():
    spec = importlib.util.spec_from_file_location(
        "windows_miner_under_test_7368", MINER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubResponse:
    """Minimal stand-in for ``requests.Response`` for the JSON branch."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


def test_submit_header_marks_slot_handled_on_http_rejection(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    def fake_post(*_args, **_kwargs):
        return _StubResponse(
            403,
            {"ok": False, "error": "no pubkey registered for miner"},
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner._last_submitted_slot is None
    success = miner.submit_header({"header": {"slot": 27455}})
    assert success is False
    # The slot is recorded even though the node rejected the header.
    assert miner._last_submitted_slot == 27455
    assert "HTTP 403" in miner.last_header_error
    assert "no pubkey registered for miner" in miner.last_header_error


def test_submit_header_marks_slot_handled_on_connection_failure(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    def fake_post(*_args, **_kwargs):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner._last_submitted_slot is None
    success = miner.submit_header({"header": {"slot": 27456}})
    assert success is False
    assert miner._last_submitted_slot == 27456
    assert "header request failed" in miner.last_header_error
    assert "connection refused" in miner.last_header_error


def test_submit_header_records_slot_on_success(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    def fake_post(*_args, **_kwargs):
        return _StubResponse(200, {"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)

    success = miner.submit_header({"header": {"slot": 27457}})
    assert success is True
    assert miner._last_submitted_slot == 27457
    assert miner.last_header_error == ""


def test_share_event_carries_diagnostic_on_failure(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    def fake_post(*_args, **_kwargs):
        return _StubResponse(
            403,
            {"ok": False, "error": "no pubkey registered for miner"},
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    events = []
    # Replay the body of the mining loop's share branch directly.
    slot = 27458
    success = miner.submit_header({"header": {"slot": slot}})
    miner.shares_submitted += 1
    if success:
        miner.shares_accepted += 1
    share_event = {
        "type":      "share",
        "slot":      slot,
        "submitted": miner.shares_submitted,
        "accepted":  miner.shares_accepted,
        "success":   success,
    }
    if not success and miner.last_header_error:
        share_event["error"] = miner.last_header_error
    events.append(share_event)

    assert events[0]["success"] is False
    assert events[0]["slot"] == 27458
    assert "no pubkey registered for miner" in events[0]["error"]


def test_share_event_omits_diagnostic_on_success(monkeypatch):
    module = _load_windows_miner()
    miner = module.RustChainMiner("RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7")

    def fake_post(*_args, **_kwargs):
        return _StubResponse(200, {"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)

    events = []
    slot = 27459
    success = miner.submit_header({"header": {"slot": slot}})
    miner.shares_submitted += 1
    if success:
        miner.shares_accepted += 1
    share_event = {
        "type":      "share",
        "slot":      slot,
        "submitted": miner.shares_submitted,
        "accepted":  miner.shares_accepted,
        "success":   success,
    }
    if not success and miner.last_header_error:
        share_event["error"] = miner.last_header_error
    events.append(share_event)

    assert events[0]["success"] is True
    assert "error" not in events[0]


def test_format_headless_event_includes_slot_and_diagnostic():
    module = _load_windows_miner()
    line = module._format_headless_event({
        "type":      "share",
        "slot":      27460,
        "submitted": 5,
        "accepted":  0,
        "success":   False,
        "error":     "HTTP 403 error=no pubkey registered for miner",
    })
    assert "slot=27460" in line
    assert "FAIL" in line
    assert "error=HTTP 403 error=no pubkey registered for miner" in line


def test_format_headless_event_omits_diagnostic_on_success():
    module = _load_windows_miner()
    line = module._format_headless_event({
        "type":      "share",
        "slot":      27461,
        "submitted": 6,
        "accepted":  6,
        "success":   True,
    })
    assert "slot=27461" in line
    assert "OK" in line
    assert "error=" not in line
