# SPDX-License-Identifier: MIT
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_fetchall.sh"
TMP_VIOLATION = ROOT / "node" / "_tmp_fetchall_guard_violation.py"


def run_guard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_fetchall_guard_passes_current_baseline():
    result = run_guard()
    assert result.returncode == 0, result.stdout
    assert "no new unannotated .fetchall()" in result.stdout


def test_fetchall_guard_blocks_new_unannotated_call():
    try:
        TMP_VIOLATION.write_text(
            "def leak(conn):\n"
            "    return conn.execute('SELECT * FROM attacker_controlled').fetchall()\n"
        )
        result = run_guard()
        assert result.returncode == 1
        assert "new unannotated .fetchall()" in result.stdout
        assert "_tmp_fetchall_guard_violation.py" in result.stdout
    finally:
        TMP_VIOLATION.unlink(missing_ok=True)


def test_fetchall_guard_allows_annotated_call():
    try:
        TMP_VIOLATION.write_text(
            "def schema_bounded(conn):\n"
            "    # fetchall-ok: pragma-result\n"
            "    return conn.execute('PRAGMA table_info(example)').fetchall()\n"
        )
        result = run_guard()
        assert result.returncode == 0, result.stdout
    finally:
        TMP_VIOLATION.unlink(missing_ok=True)


def test_fetchall_guard_fails_closed_when_required_tools_are_missing():
    result = subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={"PATH": "/nonexistent"},
    )

    assert result.returncode == 2
    assert "required command" in result.stdout
