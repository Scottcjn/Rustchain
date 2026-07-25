"""Regression tests for tools/rustchain-health.py overall verdict.

Issue #8055: the tool ran check_tip() and stored the result in the
snapshot, but both all_ok expressions (the STATUS line in render() and
the exit code in run_once()) ignored it. A dead chain tip still printed
"ALL SYSTEMS OPERATIONAL" and exited 0, silencing any monitor built on
top of this tool.

These tests drive the real CLI entrypoint (main) with a mocked fetch()
so the whole path is exercised: collect -> render -> exit code.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL_PATH = Path(__file__).parent.parent / "tools" / "rustchain-health.py"


def _load_health_module():
    name = "rustchain_health_cli"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(_TOOL_PATH))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def health_mod(monkeypatch):
    mod = _load_health_module()
    monkeypatch.setattr(mod, "_COLOR", False)
    return mod


HEALTH_BODY = {"ok": True, "version": "2.2.1-rip200", "uptime_s": 1000,
               "db_rw": True, "tip_age_slots": 0}
EPOCH_BODY = {"epoch": 424, "slot": 61000, "epoch_pot": 1.5,
              "enrolled_miners": 8}
MINERS_BODY = [{"miner_id": "dual-g4-125"}, {"miner_id": "sophia-nas-c4130"}]
TIP_BODY = {"miner": "sophia-nas-c4130", "slot": 2941199,
            "signature_prefix": "b3780cff190178456a0f"}


def _fake_fetch(responses):
    """Build a fetch() replacement keyed on URL suffix.

    responses maps an endpoint suffix to (ok, data, status).
    """
    def fetch(url, timeout=8):
        for suffix, (ok, data, status) in responses.items():
            if url.endswith(suffix):
                return ok, data, 1.0, status
        raise AssertionError(f"unexpected URL fetched: {url}")
    return fetch


def _run_cli(health_mod, monkeypatch, capsys, responses):
    monkeypatch.setattr(health_mod, "fetch", _fake_fetch(responses))
    monkeypatch.setattr(sys, "argv",
                        ["rustchain-health", "-u", "http://node.test",
                         "--no-color"])
    code = health_mod.main()
    out = capsys.readouterr().out
    return code, out


def _healthy_responses():
    return {
        "/health": (True, dict(HEALTH_BODY), 200),
        "/epoch": (True, dict(EPOCH_BODY), 200),
        "/api/miners": (True, list(MINERS_BODY), 200),
        "/headers/tip": (True, dict(TIP_BODY), 200),
    }


def test_all_healthy_exits_zero(health_mod, monkeypatch, capsys):
    code, out = _run_cli(health_mod, monkeypatch, capsys,
                         _healthy_responses())
    assert code == 0
    assert "ALL SYSTEMS OPERATIONAL" in out
    assert "ISSUES DETECTED" not in out


def test_tip_failure_exits_nonzero(health_mod, monkeypatch, capsys):
    """Regression for #8055: a failing tip check must fail the run."""
    responses = _healthy_responses()
    responses["/headers/tip"] = (False, "<urlopen error timed out>", None)
    code, out = _run_cli(health_mod, monkeypatch, capsys, responses)
    assert code != 0
    assert "ALL SYSTEMS OPERATIONAL" not in out
    assert "ISSUES DETECTED" in out


def test_tip_garbage_body_exits_nonzero(health_mod, monkeypatch, capsys):
    """Tip endpoint answers but with no identifiable tip: also a failure."""
    responses = _healthy_responses()
    responses["/headers/tip"] = (True, "<html>gateway error</html>", 200)
    code, out = _run_cli(health_mod, monkeypatch, capsys, responses)
    assert code != 0
    assert "ALL SYSTEMS OPERATIONAL" not in out


def test_tip_endpoint_not_implemented_is_not_a_failure(health_mod,
                                                       monkeypatch, capsys):
    """A node without /headers/tip (404) should not trip a false alarm."""
    responses = _healthy_responses()
    responses["/headers/tip"] = (False, "HTTP Error 404: Not Found", 404)
    code, out = _run_cli(health_mod, monkeypatch, capsys, responses)
    assert code == 0
    assert "ALL SYSTEMS OPERATIONAL" in out
    assert "not supported" in out


def test_epoch_content_missing_exits_nonzero(health_mod, monkeypatch, capsys):
    """Sibling of #8055: epoch endpoint reachable but returning no epoch
    used to show a red row while the overall verdict stayed green."""
    responses = _healthy_responses()
    responses["/epoch"] = (True, {"unexpected": "shape"}, 200)
    code, out = _run_cli(health_mod, monkeypatch, capsys, responses)
    assert code != 0
    assert "ALL SYSTEMS OPERATIONAL" not in out


def test_tip_accepts_slot_field(health_mod):
    """RIP-200 nodes report the tip as "slot", not "height"."""
    tip = {"reachable": True, "latency_ms": 1.0, "height": 2941199}
    assert health_mod.tip_verdict(tip) is True


def test_render_and_exit_code_share_one_predicate(health_mod):
    """The verdict must come from a single function so the display and
    the exit code cannot drift apart again."""
    snapshot = {
        "node": "http://node.test",
        "checked_at": "2026-01-01T00:00:00Z",
        "health": {"reachable": True, "ok": True, "latency_ms": 1.0},
        "epoch": {"reachable": True, "epoch": 1, "latency_ms": 1.0},
        "miners": {"reachable": True, "miner_count": 1, "latency_ms": 1.0},
        "tip": {"reachable": False, "error": "boom", "latency_ms": 1.0},
    }
    assert health_mod.overall_ok(snapshot) is False
    assert "ISSUES DETECTED" in health_mod.render(snapshot)
    snapshot["tip"] = {"reachable": True, "height": 5, "latency_ms": 1.0}
    assert health_mod.overall_ok(snapshot) is True
    assert "ALL SYSTEMS OPERATIONAL" in health_mod.render(snapshot)
