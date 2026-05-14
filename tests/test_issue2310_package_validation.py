# SPDX-License-Identifier: MIT

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_2310_DIR = REPO_ROOT / "bounties" / "issue-2310"


def test_issue2310_package_imports_from_parent_path():
    code = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import src; "
        "print(src.CRTPatternGenerator.__name__)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code, str(ISSUE_2310_DIR)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CRTPatternGenerator"


def test_issue2310_validator_runs_with_cp1252_stdout():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, str(ISSUE_2310_DIR / "validate_bounty_2310.py")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Final Results" in result.stdout
    assert "VALIDATION PASSED" in result.stdout
