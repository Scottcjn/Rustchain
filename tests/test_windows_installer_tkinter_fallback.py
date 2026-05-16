# SPDX-License-Identifier: MIT
import builtins
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED_MINER = ROOT / "miners" / "windows" / "installer" / "src" / "rustchain_windows_miner.py"


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
