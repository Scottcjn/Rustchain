# SPDX-License-Identifier: MIT
"""Regression coverage for the bounty verifier CLI entry paths."""

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "tools" / "bounty_verifier" / "cli.py"


def _help(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args, "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )


def test_direct_script_help_is_executable() -> None:
    result = _help(str(CLI))

    assert result.returncode == 0, result.stderr
    assert "RustChain Bounty Claim Verification Bot" in result.stdout


def test_module_help_remains_supported() -> None:
    result = _help("-m", "tools.bounty_verifier.cli")

    assert result.returncode == 0, result.stderr
    assert "RustChain Bounty Claim Verification Bot" in result.stdout
