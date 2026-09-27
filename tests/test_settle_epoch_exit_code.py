# SPDX-License-Identifier: MIT
"""Regression: node/settle_epoch.py must exit non-zero when settlement fails.

The script is run unattended; the scheduler's only signal is the exit code.
Before the fix `trigger_settlement()` swallowed every exception and the
``__main__`` block printed the (None / error-text) result and exited 0, so an
unreachable node or a 500 from /rewards/settle looked like success.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "settle_epoch.py"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def load_settle_epoch_module():
    spec = importlib.util.spec_from_file_location("settle_epoch_exit_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _patch_http(module, monkeypatch, *, get=None, post=None):
    monkeypatch.setattr(module.requests, "get",
                        get or (lambda url, timeout: FakeResponse(payload={"epoch": 42})))
    monkeypatch.setattr(module.requests, "post",
                        post or (lambda url, json, timeout: FakeResponse(payload={"ok": True})))


def test_main_exits_zero_on_successful_settlement(monkeypatch):
    module = load_settle_epoch_module()
    _patch_http(module, monkeypatch)
    assert module.main() == 0


def test_main_exits_nonzero_when_node_unreachable(monkeypatch, capsys):
    module = load_settle_epoch_module()

    def raise_conn(_url, timeout):
        raise RuntimeError("connection refused")

    _patch_http(module, monkeypatch, get=raise_conn)
    assert module.main() != 0
    assert "Error: connection refused" in capsys.readouterr().out  # logging kept


def test_main_exits_nonzero_on_http_error_from_settle(monkeypatch):
    module = load_settle_epoch_module()
    _patch_http(module, monkeypatch,
                post=lambda url, json, timeout: FakeResponse(status_code=500, text="boom"))
    assert module.main() != 0


def test_main_exits_nonzero_when_node_reports_ok_false(monkeypatch):
    module = load_settle_epoch_module()
    _patch_http(module, monkeypatch,
                post=lambda url, json, timeout: FakeResponse(
                    status_code=200, payload={"ok": False, "error": "already settled"}))
    assert module.main() != 0


def test_main_exits_nonzero_on_malformed_epoch_response(monkeypatch):
    module = load_settle_epoch_module()
    _patch_http(module, monkeypatch, get=lambda url, timeout: FakeResponse(payload={"height": 1}))
    assert module.main() != 0


def test_script_process_exit_code_nonzero_when_node_down():
    """End-to-end: run the real script against a port nothing listens on.
    On main this exits 0 (the bug); with the fix it exits 1."""
    env = {**os.environ, "RC_NODE_URL": "http://127.0.0.1:9"}  # discard port; refused
    proc = subprocess.run([sys.executable, str(MODULE_PATH)], env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0, (
        f"settle_epoch.py exited {proc.returncode} although the node was unreachable\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}")
    assert "Error:" in proc.stdout
