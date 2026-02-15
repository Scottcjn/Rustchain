#!/usr/bin/env python3
"""
BCOS SPDX header enforcement (minimal).

Policy:
- Only enforce on *newly added* files in a PR.
- For code-like extensions, require an SPDX-License-Identifier line near the top.

This avoids rewriting legacy files while still preventing new unlicensed blobs.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


CODE_EXTS = {
    ".py",
    ".sh",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".go",
}

SPDX_RE = re.compile(r"SPDX-License-Identifier:\s*[A-Za-z0-9.\-+]+")


def _run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def _git_diff_name_status(base_ref: str) -> List[Tuple[str, str]]:
    out = _run(["git", "diff", "--name-status", f"{base_ref}...HEAD"])
    rows: List[Tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts
        rows.append((status.strip(), path.strip()))
    return rows


def _top_lines(path: Path, max_lines: int = 25) -> List[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = []
            for _ in range(max_lines):
                line = f.readline()
                if not line:
                    break
                lines.append(line.rstrip("\n"))
            return lines
    except Exception:
        return []


def _has_spdx(lines: List[str]) -> bool:
    if not lines:
        return False
    # Skip leading shebang on scripts.
    if lines[0].startswith("#!"):
        lines = lines[1:]
    # Look near the top only.
    snippet = "\n".join(lines[:20])
    return bool(SPDX_RE.search(snippet))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-ref",
        default=os.environ.get("BCOS_BASE_REF", ""),
        help="Git base ref to diff against (e.g. origin/main).",
    )
    args = ap.parse_args(argv)

    base_ref = (args.base_ref or "").strip()
    if not base_ref:
        base = os.environ.get("GITHUB_BASE_REF", "main")
        base_ref = f"origin/{base}"

    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    # Ensure base ref exists locally.
    try:
        _run(["git", "rev-parse", "--verify", base_ref])
    except Exception:
        _run(["git", "fetch", "origin", base_ref.split("/", 1)[1], "--depth=1"])

    changes = _git_diff_name_status(base_ref)
    added = [p for st, p in changes if st == "A"]

    failures: List[str] = []
    for rel in added:
        path = repo_root / rel
        ext = path.suffix.lower()
        if ext not in CODE_EXTS:
            continue
        lines = _top_lines(path)
        if not _has_spdx(lines):
            failures.append(rel)

    if failures:
        print("BCOS SPDX check failed. Add an SPDX header to the following new files:", file=sys.stderr)
        for f in failures:
            print(f"- {f}", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("# SPDX-License-Identifier: MIT", file=sys.stderr)
        return 2

    print("BCOS SPDX check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

