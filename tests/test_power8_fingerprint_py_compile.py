# SPDX-License-Identifier: MIT
import subprocess
import sys
from pathlib import Path


def test_power8_fingerprint_checks_compile_with_syntax_warnings_as_errors():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::SyntaxWarning",
            "-m",
            "py_compile",
            "miners/power8/fingerprint_checks_power8.py",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
