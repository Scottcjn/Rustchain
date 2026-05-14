# SPDX-License-Identifier: MIT
"""Regression tests for the BoTTube onboarding CLI."""

import subprocess
import sys
from pathlib import Path


def test_welcome_template_cli_does_not_crash():
    script = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "bottube_onboarding"
        / "__init__.py"
    )

    result = subprocess.run(
        [sys.executable, str(script), "--show-template", "welcome"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "demo_agent" in result.stdout
