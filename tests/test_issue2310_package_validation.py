# SPDX-License-Identifier: Apache-2.0
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ISSUE_DIR = ROOT / "bounties" / "issue-2310"


def test_crt_attestation_package_imports_from_parent_path():
    pytest.importorskip("numpy")

    code = (
        "import sys; "
        f"sys.path.insert(0, {str(ISSUE_DIR)!r}); "
        "import src; "
        "assert src.CRTAttestationSubmitter; "
        "assert src.CRTPatternGenerator"
    )

    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT)


def test_issue2310_validator_does_not_crash_under_cp1252_stdout():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, "validate_bounty_2310.py"],
        cwd=ISSUE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    combined_output = result.stdout + result.stderr
    assert "UnicodeEncodeError" not in combined_output
    assert "Final Results" in combined_output
