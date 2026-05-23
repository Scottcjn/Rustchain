# SPDX-License-Identifier: MIT
import subprocess
import sys


def test_setup_miner_help_exits_before_setup_side_effects():
    result = subprocess.run(
        [sys.executable, "setup_miner.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "Set up the RustChain Universal Miner" in result.stdout
    assert "RustChain Miner Setup" not in result.stdout
    assert "Creating directories" not in result.stdout
    assert "Downloading RustChain miner" not in result.stdout
    assert result.stderr == ""
