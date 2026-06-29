# SPDX-License-Identifier: MIT
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_fetchall.sh"
TMP_VIOLATION = ROOT / "node" / "_tmp_fetchall_guard_violation.py"
TMP_IGNORED = ROOT / "node" / "_tmp_fetchall_guard_genesis.py"
TMP_BASELINE = ROOT / "scripts" / "baselines" / "_tmp_fetchall_stale_baseline.txt"


def run_guard(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
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


def test_fetchall_guard_blocks_whitespace_before_call_parens():
    try:
        TMP_VIOLATION.write_text(
            "def leak(conn):\n"
            "    return conn.execute('SELECT * FROM attacker_controlled').fetchall ()\n"
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


def test_fetchall_guard_matches_windows_style_baseline_paths():
    try:
        TMP_VIOLATION.write_text(
            "def leak(conn):\n"
            "    return conn.execute('SELECT * FROM attacker_controlled').fetchall()\n"
        )
        current = run_guard("--print-baseline")
        assert current.returncode == 0, current.stdout
        windows_style = current.stdout.replace(
            "node/_tmp_fetchall_guard_violation.py:",
            r"node\_tmp_fetchall_guard_violation.py:",
        )
        TMP_BASELINE.write_text(windows_style)

        result = run_guard(env={"PATH": "/usr/bin:/bin", "FETCHALL_BASELINE": str(TMP_BASELINE)})
        assert result.returncode == 0, result.stdout
    finally:
        TMP_VIOLATION.unlink(missing_ok=True)
        TMP_BASELINE.unlink(missing_ok=True)


def test_fetchall_guard_ignores_gitignored_generated_files():
    try:
        TMP_IGNORED.write_text(
            "def ignored_generated(conn):\n"
            "    return conn.execute('SELECT * FROM ignored_genesis').fetchall()\n"
        )

        result = run_guard()
        assert result.returncode == 0, result.stdout

        fallback = run_guard(env={"PATH": "/usr/bin:/bin"})
        assert fallback.returncode == 0, fallback.stdout
    finally:
        TMP_IGNORED.unlink(missing_ok=True)


def test_fetchall_guard_detects_stale_baseline_entries():
    try:
        current = run_guard("--print-baseline")
        assert current.returncode == 0, current.stdout
        TMP_BASELINE.write_text(current.stdout + "node/phantom.py:1:cursor.fetchall()\n")
        result = run_guard(env={"PATH": "/usr/bin:/bin", "FETCHALL_BASELINE": str(TMP_BASELINE)})
        assert result.returncode == 1
        assert "stale entries" in result.stdout
        assert "node/phantom.py" in result.stdout
    finally:
        TMP_BASELINE.unlink(missing_ok=True)
