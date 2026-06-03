# SPDX-License-Identifier: MIT

import subprocess
import sys
from pathlib import Path


def test_mac_miner_v24_version_does_not_require_optional_helpers():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "miners" / "macos" / "rustchain_mac_miner_v2.4.py"

    result = subprocess.run(
        [sys.executable, str(script), "--version"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "RustChain Mac Miner v2.4.0" in result.stdout
    assert "NameError" not in result.stderr
