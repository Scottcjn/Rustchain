"""Tests for scripts/check_links.py (relative-link + fragment checker)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_links.py"


def run_check(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_relative_link_and_anchor_passes(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# Getting Started\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[guide](guide.md) and [section](guide.md#getting-started)\n",
        encoding="utf-8",
    )

    result = run_check(tmp_path, "README.md")

    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_file_fails(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("[nope](missing.md)\n", encoding="utf-8")

    result = run_check(tmp_path, "README.md")

    assert result.returncode == 1
    assert "missing file" in result.stdout


def test_missing_anchor_fails(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# Getting Started\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[nope](guide.md#does-not-exist)\n", encoding="utf-8"
    )

    result = run_check(tmp_path, "README.md")

    assert result.returncode == 1
    assert "missing anchor" in result.stdout


def test_external_links_ignored(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[site](https://example.com) [mail](mailto:x@example.com)\n",
        encoding="utf-8",
    )

    result = run_check(tmp_path, "README.md")

    assert result.returncode == 0, result.stdout + result.stderr
