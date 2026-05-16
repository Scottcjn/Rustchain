# SPDX-License-Identifier: MIT
import subprocess
import sys
from pathlib import Path


def test_linux_miner_help_documents_dry_run():
    miner = Path(__file__).resolve().parents[1] / "miners" / "linux" / "rustchain_linux_miner.py"

    result = subprocess.run(
        [sys.executable, str(miner), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    help_text = " ".join(result.stdout.split())

    assert "--dry-run" in help_text
    assert "print hardware fingerprint info" in help_text
    assert "do not start mining" in help_text
