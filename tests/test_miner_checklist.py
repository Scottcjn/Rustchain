# SPDX-License-Identifier: MIT
"""Unit tests for the miner pre-flight checklist helper."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "miner_checklist.py"


def load_module():
    spec = importlib.util.spec_from_file_location("miner_checklist_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_prints_pass_and_returns_condition(capsys):
    module = load_module()

    assert module.check("clawrtc installed", True) is True

    assert "[PASS] clawrtc installed" in capsys.readouterr().out


def test_check_prints_fail_and_returns_false(capsys):
    module = load_module()

    assert module.check("Wallet exists", False) is False

    assert "[FAIL] Wallet exists" in capsys.readouterr().out


def test_preflight_reports_ready_when_all_checks_pass(capsys):
    module = load_module()

    with (
        patch.object(module.shutil, "which", return_value="/usr/local/bin/clawrtc"),
        patch.object(module.os.path, "exists", return_value=True),
        patch.object(module.shutil, "disk_usage", return_value=SimpleNamespace(free=2_000_000_000)),
        patch.object(module.urllib.request, "urlopen", return_value=object()),
    ):
        module.preflight()

    output = capsys.readouterr().out
    assert "[PASS] clawrtc installed" in output
    assert "[PASS] Wallet exists" in output
    assert "[PASS] Disk > 1GB free" in output
    assert "[PASS] Node reachable" in output
    assert "Ready to mine!" in output


def test_preflight_reports_failures_when_dependencies_are_missing(capsys):
    module = load_module()

    with (
        patch.object(module.shutil, "which", return_value=None),
        patch.object(module.os.path, "exists", return_value=False),
        patch.object(module.shutil, "disk_usage", return_value=SimpleNamespace(free=500_000_000)),
        patch.object(module.urllib.request, "urlopen", side_effect=OSError("offline")),
    ):
        module.preflight()

    output = capsys.readouterr().out
    assert "[FAIL] clawrtc installed" in output
    assert "[FAIL] Wallet exists" in output
    assert "[FAIL] Disk > 1GB free" in output
    assert "[FAIL] Node reachable" in output
    assert "Fix issues above first." in output


def test_preflight_calls_health_endpoint_with_timeout_and_context():
    module = load_module()
    urlopen_calls = []

    def fake_urlopen(*args, **kwargs):
        urlopen_calls.append((args, kwargs))
        return object()

    with (
        patch.object(module.shutil, "which", return_value="/usr/local/bin/clawrtc"),
        patch.object(module.os.path, "exists", return_value=True),
        patch.object(module.shutil, "disk_usage", return_value=SimpleNamespace(free=2_000_000_000)),
        patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen),
    ):
        module.preflight()

    args, kwargs = urlopen_calls[0]
    assert args == ("https://rustchain.org/health",)
    assert kwargs["timeout"] == 5
    assert kwargs["context"] is not None
