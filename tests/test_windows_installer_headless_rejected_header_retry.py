# SPDX-License-Identifier: MIT
"""Regression tests for Issue #7368 — packaged Windows headless miner.

``miners/windows/installer/src/rustchain_windows_miner.py`` is the copy that
``RustChainMiner.spec`` / ``installer/build_miner.py`` compile into the shipped
Windows executable. It kept the pre-fix behavior after the standalone miner was
fixed: ``submit_header`` returned a bare ``False``, so the node's rejection
reason was discarded and ``_mine_loop`` resubmitted the same rejected header
every 10 seconds for the whole eligibility window.

These tests prove, for the packaged copy:

* a terminal rejection (400/403) records the node's diagnostic and marks the
  lottery slot handled — no resubmission of that slot;
* a temporary failure (connection blip, 5xx, 429/408/425) is classified
  retryable and gets bounded exponential backoff instead of a hot loop;
* ``_mine_loop`` performs exactly one POST for a terminal-rejected slot across
  several polls;
* the headless line carries the diagnostic plus its retry class.
"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED_MINER_PATH = (
    ROOT / "miners" / "windows" / "installer" / "src" / "rustchain_windows_miner.py"
)

WALLET = "RTC02811ff5e2bb4bb4b95eee44c5429cd9525496e7"


def _load_packaged_miner():
    spec = importlib.util.spec_from_file_location(
        "packaged_windows_miner_under_test_7368", PACKAGED_MINER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_miner(module, monkeypatch):
    """Build a real miner instance without touching Windows hardware probes."""
    monkeypatch.setattr(
        module.RustChainMiner,
        "_get_hw_info",
        lambda self: {"family": "windows", "arch": "x86_64"},
    )
    monkeypatch.setattr(
        module.RustChainMiner, "_run_fingerprint_checks", lambda self: None
    )
    miner = module.RustChainMiner(WALLET)
    miner.node_url = "https://rustchain.org"
    return miner


class _StubResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


def test_terminal_rejection_marks_slot_handled_and_keeps_diagnostic(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)

    def fake_post(*_args, **_kwargs):
        return _StubResponse(400, {"ok": False, "error": "missing fields"})

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner._last_submitted_slot is None
    success = miner.submit_header({"miner_id": miner.miner_id, "hash": "abc"}, 49029)
    assert success is False
    # The rejected slot counts as handled: the header is never resent unchanged.
    assert miner._last_submitted_slot == 49029
    assert miner.last_header_retryable is False
    assert miner.header_retry_in_seconds == 0
    assert miner._header_submission_due(49029, now=1_000_000.0) is False
    # The server's own diagnostic survives, verbatim.
    assert "HTTP 400" in miner.last_header_error
    assert "missing fields" in miner.last_header_error


def _status_post(status):
    """POST stub that always answers with *status*."""

    def fake_post(*_args, **_kwargs):
        return _StubResponse(status, {"ok": False})

    return fake_post


def test_bad_signature_is_terminal_but_node_outage_is_retryable(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)

    for status, expected_retryable in (
        (403, False),
        (408, True),
        (429, True),
        (500, True),
        (503, True),
    ):
        monkeypatch.setattr(module.requests, "post", _status_post(status))
        miner.submit_header({"header": {}}, 49100)
        assert miner.last_header_retryable is expected_retryable


def test_connection_failure_schedules_bounded_backoff(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(module.random, "uniform", lambda *_args: 1.0)

    def fake_post(*_args, **_kwargs):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header({"miner_id": miner.miner_id}, 49030) is False
    assert miner._last_submitted_slot is None
    assert miner.last_header_retryable is True
    assert miner.header_retry_in_seconds == module.HEADER_RETRY_BASE_SECONDS
    assert miner._header_submission_due(49030, now=109.9) is False
    assert miner._header_submission_due(49030, now=110.1) is True

    # Second consecutive failure doubles the delay: 10s -> 20s.
    miner.submit_header({"miner_id": miner.miner_id}, 49030)
    assert miner.header_retry_in_seconds == 20

    # Backoff never exceeds the documented cap.
    for _ in range(12):
        miner.submit_header({"miner_id": miner.miner_id}, 49030)
    assert miner.header_retry_in_seconds <= module.HEADER_RETRY_CAP_SECONDS


def test_success_clears_retry_state_and_holds_the_slot(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)

    def fake_post(*_args, **_kwargs):
        return _StubResponse(200, {"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header({"miner_id": miner.miner_id}, 49031) is True
    assert miner._last_submitted_slot == 49031
    assert miner.last_header_error == ""
    assert miner._header_retry_slot is None
    assert miner._header_submission_due(49031) is False


def test_mine_loop_submits_terminal_rejected_slot_only_once(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)

    posts = []

    def fake_post(_url, **kwargs):
        posts.append(kwargs["json"])
        return _StubResponse(400, {"ok": False, "error": "missing fields"})

    def fake_get(_url, **_kwargs):
        return _StubResponse(200, {"eligible": True, "slot": 49032})

    monkeypatch.setattr(module.requests, "post", fake_post)
    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(miner, "attest", lambda: True)
    monkeypatch.setattr(miner, "enroll", lambda: True)

    polls = []

    def fake_sleep(_seconds):
        polls.append(_seconds)
        if len(polls) >= 3:
            miner.mining = False

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    events = []
    miner.mining = True
    miner._mine_loop(events.append)

    # Three eligible polls, one POST: the rejected header is not hot-retried.
    assert len(posts) == 1
    share = [evt for evt in events if evt.get("type") == "share"]
    assert len(share) == 1
    assert share[0]["slot"] == 49032
    assert share[0]["success"] is False
    assert "missing fields" in share[0]["error"]
    assert share[0]["retryable"] is False


def test_headless_line_carries_diagnostic_and_class(monkeypatch):
    module = _load_packaged_miner()
    miner = _make_miner(module, monkeypatch)

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_a, **_k: _StubResponse(400, {"ok": False, "error": "missing fields"}),
    )
    miner.submit_header({"miner_id": miner.miner_id}, 49033)
    terminal = module._format_headless_event(
        {
            "type": "share",
            "slot": 49033,
            "submitted": 1,
            "accepted": 0,
            "success": False,
            "error": miner.last_header_error,
            "retryable": miner.last_header_retryable,
        }
    )
    assert "missing fields" in terminal
    assert "class=terminal no_retry" in terminal

    monkeypatch.setattr(module.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(module.random, "uniform", lambda *_a: 1.0)

    def fake_fail(*_args, **_kwargs):
        raise OSError("blip")

    monkeypatch.setattr(module.requests, "post", fake_fail)
    miner.submit_header({"miner_id": miner.miner_id}, 49034)
    retryable = module._format_headless_event(
        {
            "type": "share",
            "slot": 49034,
            "submitted": 2,
            "accepted": 0,
            "success": False,
            "error": miner.last_header_error,
            "retryable": miner.last_header_retryable,
            "retry_in_seconds": round(miner.header_retry_in_seconds, 1),
        }
    )
    assert "class=retryable retry_in=" in retryable
    assert "header request failed" in retryable
