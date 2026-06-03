# SPDX-License-Identifier: MIT

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE2310_ROOT = REPO_ROOT / "bounties" / "issue-2310"


def test_issue2310_package_imports_from_parent_path():
    issue_path = str(ISSUE2310_ROOT)
    code = (
        "import sys; "
        f"sys.path.insert(0, {issue_path!r}); "
        "import src; "
        "print(src.__file__); "
        "print(src.__all__[0])"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = result.stdout.strip().splitlines()
    assert Path(stdout[0]).resolve() == ISSUE2310_ROOT / "src" / "__init__.py"
    assert stdout[1] == "CRTPatternGenerator"


def test_issue2310_validator_runs_with_cp1252_stdout():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [sys.executable, str(ISSUE2310_ROOT / "validate_bounty_2310.py")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Final Results" in result.stdout
    assert "VALIDATION PASSED" in result.stdout
