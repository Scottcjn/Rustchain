# SPDX-License-Identifier: MIT
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_setup_miner_help_is_non_mutating(tmp_path):
    home = tmp_path / "home"
    home.mkdir()

    result = subprocess.run(
        [sys.executable, str(ROOT / "setup_miner.py"), "--help"],
        cwd=ROOT,
        env={"HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "RustChain Miner Setup" in result.stdout
    assert not (home / "rustchain_miner").exists()
