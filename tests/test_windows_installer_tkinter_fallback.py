# SPDX-License-Identifier: MIT
import builtins
import importlib.util
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED_MINER = ROOT / "miners" / "windows" / "installer" / "src" / "rustchain_windows_miner.py"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 400

    def json(self):
        return self._payload


def load_packaged_miner():
    spec = importlib.util.spec_from_file_location(
        "packaged_windows_miner_under_test",
        PACKAGED_MINER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_miner(module):
    miner = module.RustChainMiner.__new__(module.RustChainMiner)
    miner.wallet_address = "RTCwallet"
    miner.miner_id = "windows_local"
    miner.node_url = "https://node.example"
    return miner


def test_packaged_miner_help_works_without_tkinter(monkeypatch, capsys):
    real_import = builtins.__import__

    def block_tkinter(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tkinter" or name.startswith("tkinter."):
            raise ModuleNotFoundError("No module named 'tkinter'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", block_tkinter)
    monkeypatch.setattr(sys, "argv", [str(PACKAGED_MINER), "--help"])

    try:
        runpy.run_path(str(PACKAGED_MINER), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert "--headless" in captured.out
    assert "--wallet" in captured.out


def test_packaged_miner_eligibility_uses_configured_node(monkeypatch):
    module = load_packaged_miner()
    miner = make_miner(module)
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({"eligible": True})

    monkeypatch.setattr(module.requests, "get", fake_get)

    assert miner.check_eligibility() is True
    assert captured == {
        "url": "https://node.example/lottery/eligibility",
        "params": {"miner_id": "windows_local"},
        "timeout": 10,
        "verify": module.TLS_VERIFY,
    }


def test_packaged_miner_submit_uses_configured_node(monkeypatch):
    module = load_packaged_miner()
    miner = make_miner(module)
    captured = {}
    header = {"miner_id": "windows_local", "hash": "abc123"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert miner.submit_header(header) is True
    assert captured == {
        "url": "https://node.example/headers/ingest_signed",
        "json": header,
        "timeout": 5,
        "verify": module.TLS_VERIFY,
    }
