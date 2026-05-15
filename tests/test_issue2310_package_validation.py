# SPDX-License-Identifier: MIT

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_issue2310_package_imports_from_parent_path():
    package_path = REPO_ROOT / "bounties" / "issue-2310"
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(package_path)!r}); "
        "import src; "
        "print(src.CRTPatternGenerator.__name__)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
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
    validator_path = REPO_ROOT / "bounties" / "issue-2310" / "validate_bounty_2310.py"

    result = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Final Results" in result.stdout
    assert "VALIDATION PASSED" in result.stdout
