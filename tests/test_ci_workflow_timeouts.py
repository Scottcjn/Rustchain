#!/usr/bin/env python3
"""Regression tests for Bounty #16472: CI job & per-step timeouts + timeout-vs-failure diagnostic."""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LABELER_YML = REPO_ROOT / ".github" / "workflows" / "labeler.yml"


def test_ci_workflow_defines_job_and_per_step_timeouts():
    content = CI_YML.read_text(encoding="utf-8")
    assert "timeout-minutes: 10" in content
    # Every step in `test` job should have an explicit timeout-minutes
    step_timeouts = re.findall(r"^\s+timeout-minutes:\s*(\d+)", content, flags=re.MULTILINE)
    assert len(step_timeouts) >= 12, f"Expected >= 12 timeout-minutes declarations in ci.yml, found {len(step_timeouts)}"
    for val in step_timeouts:
        assert 1 <= int(val) <= 10


def test_ci_pip_installs_enforce_network_timeout_and_retries():
    content = CI_YML.read_text(encoding="utf-8")
    pip_lines = [
        line.strip()
        for line in content.splitlines()
        if "pip install" in line and not line.strip().startswith("echo")
    ]
    assert len(pip_lines) >= 4
    for line in pip_lines:
        assert "--timeout 60" in line, f"pip install missing --timeout 60: {line}"
        assert "--retries 3" in line, f"pip install missing --retries 3: {line}"


def test_ci_distinguishes_timeout_cancellation_from_code_failure():
    content = CI_YML.read_text(encoding="utf-8")
    assert "ci-timeout-diagnostic:" in content
    assert 'if [ "$TEST_RESULT" = "cancelled" ]; then' in content
    assert "CI Runner or Step Timeout" in content
    assert "Contributor Code or Test Failure" in content


def test_labeler_workflow_defines_job_and_step_timeout():
    content = LABELER_YML.read_text(encoding="utf-8")
    assert "timeout-minutes: 5" in content
    assert "timeout-minutes: 3" in content
