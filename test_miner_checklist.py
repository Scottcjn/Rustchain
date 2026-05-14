# SPDX-License-Identifier: MIT

from types import SimpleNamespace

import tools.miner_checklist as checklist


def test_check_prints_pass_or_fail(capsys):
    assert checklist.check("Wallet exists", True) is True
    assert checklist.check("Node reachable", False) is False

    assert capsys.readouterr().out.splitlines() == [
        "  [PASS] Wallet exists",
        "  [FAIL] Node reachable",
    ]


def test_preflight_prints_ready_when_all_checks_pass(monkeypatch, capsys):
    requested = {}

    def fake_urlopen(url, timeout, context):
        requested["url"] = url
        requested["timeout"] = timeout
        requested["context"] = context
        return SimpleNamespace()

    monkeypatch.setattr(checklist.shutil, "which", lambda name: "C:/bin/clawrtc.exe")
    monkeypatch.setattr(checklist.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(
        checklist.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=2_000_000_000),
    )
    monkeypatch.setattr(checklist.urllib.request, "urlopen", fake_urlopen)

    checklist.preflight()

    output = capsys.readouterr().out
    assert "Miner Pre-Flight Checklist" in output
    assert "  [PASS] Python 3.8+" in output
    assert "  [PASS] clawrtc installed" in output
    assert "  [PASS] Wallet exists" in output
    assert "  [PASS] Disk > 1GB free" in output
    assert "  [PASS] Node reachable" in output
    assert "Ready to mine!" in output
    assert requested["url"] == "https://rustchain.org/health"
    assert requested["timeout"] == 5


def test_preflight_prints_action_needed_when_checks_fail(monkeypatch, capsys):
    def fail_urlopen(_url, timeout, context):
        raise OSError("offline")

    monkeypatch.setattr(checklist.shutil, "which", lambda _name: None)
    monkeypatch.setattr(checklist.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(
        checklist.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=1),
    )
    monkeypatch.setattr(checklist.urllib.request, "urlopen", fail_urlopen)

    checklist.preflight()

    output = capsys.readouterr().out
    assert "  [FAIL] clawrtc installed" in output
    assert "  [FAIL] Wallet exists" in output
    assert "  [FAIL] Disk > 1GB free" in output
    assert "  [FAIL] Node reachable" in output
    assert "Fix issues above first." in output
