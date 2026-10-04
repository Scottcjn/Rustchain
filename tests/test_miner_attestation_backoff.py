# SPDX-License-Identifier: MIT
"""Attestation retries must back off instead of exhausting the node's
10-submissions-per-hour limit (409 REPLAY_ATTACK_BLOCKED). Reported by AgenteTor.
"""

from pathlib import Path
import importlib.util

import pytest


ROOT = Path(__file__).resolve().parents[1]
MAC_PATH = ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py"
LINUX_PATH = ROOT / "miners" / "linux" / "rustchain_linux_miner.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mac():
    return _load(MAC_PATH, "mac_miner_v25_attest_backoff")


@pytest.fixture(scope="module")
def linux():
    return _load(LINUX_PATH, "linux_miner_attest_backoff")


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


REPLAY_409 = FakeResponse(
    {
        "ok": False,
        "error": "rate_limit_exceeded",
        "code": "REPLAY_ATTACK_BLOCKED",
        "details": {"limit": 10, "current_count": 10, "retry_after_seconds": 1500},
    },
    status_code=409,
)


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.now = start

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# ── shared helper ─────────────────────────────────────────────


@pytest.mark.parametrize("module_fixture", ["mac", "linux"])
def test_retry_after_parsed_from_409_body_and_header(request, module_fixture):
    mod = request.getfixturevalue(module_fixture)
    assert mod._retry_after_from_response(REPLAY_409) == 1500
    assert mod._retry_after_from_response(FakeResponse({}, 429, {"Retry-After": "42"})) == 42
    assert mod._retry_after_from_response(FakeResponse({"error": "x"}, 500)) is None
    assert mod._retry_after_from_response(
        FakeResponse({"details": {"retry_after_seconds": "soon"}}, 409)
    ) is None


@pytest.mark.parametrize("module_fixture", ["mac", "linux"])
def test_backoff_is_exponential_capped_and_resets(request, module_fixture, capsys):
    mod = request.getfixturevalue(module_fixture)
    cls = mod.MacMiner if module_fixture == "mac" else mod.LocalMiner
    miner = cls.__new__(cls)

    delays = []
    for _ in range(7):
        miner._record_attest_outcome(False, now=0.0)
        delays.append(miner._next_attest_at)
    assert delays == [30, 60, 120, 240, 480, 900, 900]

    miner._record_attest_outcome(True, now=0.0)
    assert miner._attest_failures == 0
    assert miner._next_attest_at == 0.0


@pytest.mark.parametrize("module_fixture", ["mac", "linux"])
def test_node_retry_after_overrides_shorter_backoff(request, module_fixture, capsys):
    mod = request.getfixturevalue(module_fixture)
    cls = mod.MacMiner if module_fixture == "mac" else mod.LocalMiner
    miner = cls.__new__(cls)
    miner._last_attest_retry_after = 1500
    miner._record_attest_outcome(False, now=100.0)
    assert miner._next_attest_at == 1600.0
    assert miner._attestation_allowed(now=1599.0) is False
    assert miner._attestation_allowed(now=1600.0) is True


@pytest.mark.parametrize("module_fixture", ["mac", "linux"])
def test_hourly_budget_stays_below_node_limit(request, module_fixture, capsys):
    mod = request.getfixturevalue(module_fixture)
    cls = mod.MacMiner if module_fixture == "mac" else mod.LocalMiner
    assert mod.ATTEST_MAX_PER_HOUR < 10
    miner = cls.__new__(cls)
    miner._attest_submissions = [1000.0 + i for i in range(mod.ATTEST_MAX_PER_HOUR)]
    assert miner._attestation_allowed(now=2000.0) is False
    assert miner._next_attest_at == 4600.0  # oldest submission + 1 hour
    assert miner._attestation_allowed(now=4600.0) is True


# ── macOS miner ───────────────────────────────────────────────


class Mac409Transport:
    def __init__(self):
        self.posts = []

    def post(self, path, json=None, timeout=None):
        self.posts.append(path)
        if path == "/attest/challenge":
            return FakeResponse({"nonce": "nonce-1"})
        return REPLAY_409


def _mac_miner(mac):
    miner = mac.MacMiner.__new__(mac.MacMiner)
    miner.miner_id = "g4-host"
    miner.wallet = "RTCwallet"
    miner.hw_info = {
        "family": "PowerPC", "arch": "G4", "model": "PowerBook", "cpu": "G4",
        "cores": 1, "memory_gb": 1, "serial": "SERIAL", "mac": "00:11:22:33:44:55",
        "macs": ["00:11:22:33:44:55"], "hostname": "host",
    }
    miner.fingerprint_data = {"all_passed": True, "checks": {}}
    miner.fingerprint_passed = True
    miner.signing_key = None
    miner.signing_pubkey_hex = None
    miner.attestation_valid_until = 0
    miner.last_entropy = {}
    miner.shares_submitted = 0
    miner.shares_accepted = 0
    miner.shutdown_requested = False
    return miner


def test_mac_409_honours_retry_after_without_resubmitting(mac, monkeypatch, capsys):
    clock = FakeClock()
    monkeypatch.setattr(mac.time, "time", clock.time)
    monkeypatch.setattr(mac, "collect_entropy", lambda *a, **k: {"variance_ns": 1.0})
    miner = _mac_miner(mac)
    miner.transport = Mac409Transport()

    assert miner.try_attest() is False
    assert miner.transport.posts == ["/attest/challenge", "/attest/submit"]
    assert miner._next_attest_at == clock.now + 1500

    clock.advance(1499)
    assert miner.try_attest() is False
    assert len(miner.transport.posts) == 2  # nothing sent while backing off


def _run_mac_loop(mac, monkeypatch, miner, clock, attest, eligibility, seconds):
    monkeypatch.setattr(mac.time, "time", clock.time)
    miner.attest = attest
    miner.check_eligibility = lambda: eligibility
    miner._detect_sleep_wake = lambda: False
    deadline = clock.now + seconds

    def fake_sleep(secs, interval=1.0):
        clock.advance(secs)
        if clock.now >= deadline:
            miner.shutdown_requested = True

    miner.sleep_until_shutdown = fake_sleep
    miner.run()


def test_mac_not_attested_respects_valid_attestation(mac, monkeypatch, capsys):
    """Issue scenario: node keeps answering not_attested. The old loop
    re-attested every 10 s (61 calls in 10 minutes); now only on TTL expiry."""
    clock = FakeClock()
    miner = _mac_miner(mac)
    calls = []

    def attest_ok():
        calls.append(clock.now)
        miner.attestation_valid_until = clock.now + mac.ATTESTATION_TTL
        return True

    _run_mac_loop(mac, monkeypatch, miner, clock, attest_ok,
                  {"eligible": False, "reason": "not_attested", "slot": 1}, seconds=600)

    assert len(calls) == 2  # initial + one re-attest at the 580 s expiry
    assert calls[1] - calls[0] >= mac.ATTESTATION_TTL


def test_mac_failing_attestation_stays_under_node_limit_for_an_hour(mac, monkeypatch, capsys):
    clock = FakeClock()
    miner = _mac_miner(mac)
    calls = []

    def attest_409():
        calls.append(clock.now)
        miner._attest_submission_log().append(clock.now)
        miner._last_attest_retry_after = None  # worst case: no hint from node
        return False

    _run_mac_loop(mac, monkeypatch, miner, clock, attest_409,
                  {"eligible": False, "reason": "not_attested", "slot": 1}, seconds=3600)

    assert 1 < len(calls) <= mac.ATTEST_MAX_PER_HOUR
    gaps = [b - a for a, b in zip(calls, calls[1:])]
    assert gaps == sorted(gaps)  # backoff never shrinks while failing
    assert gaps[0] >= mac.ATTEST_BACKOFF_BASE


# ── Linux miner ───────────────────────────────────────────────


def test_linux_enroll_does_not_reattest_during_backoff(linux, monkeypatch, capsys):
    clock = FakeClock()
    monkeypatch.setattr(linux.time, "time", clock.time)
    miner = linux.LocalMiner.__new__(linux.LocalMiner)
    miner.attestation_valid_until = 0
    calls = []

    def attest_409():
        calls.append(clock.now)
        miner._last_attest_retry_after = 1500
        return False

    miner.attest = attest_409

    assert miner.enroll() is False
    clock.advance(60)  # mine() retries enroll every 60 s
    assert miner.enroll() is False
    assert len(calls) == 1
    assert "next attempt in" in capsys.readouterr().out
