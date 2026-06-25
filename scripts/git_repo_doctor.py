#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACK_CORRUPTION_MARKERS = (
    "too short to be a packfile",
    "index-pack failed",
    "pack checksum mismatch",
    "packfile",
)
OBJECT_CORRUPTION_MARKERS = (
    "bad object",
    "object file",
    "loose object",
    "invalid sha1 pointer",
    "unable to read",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tail_text(value: str | bytes | None, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def classify_git_output(text: str) -> str | None:
    lower = (text or "").lower()
    if "too short to be a packfile" in lower:
        return "git_packfile_truncated"
    if any(marker in lower for marker in PACK_CORRUPTION_MARKERS):
        return "git_packfile_corruption"
    if "object file" in lower and "is empty" in lower:
        return "git_object_file_empty"
    if any(marker in lower for marker in OBJECT_CORRUPTION_MARKERS):
        return "git_object_database_corruption"
    return None


def run_git(repo_path: Path, args: list[str], timeout: float) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return {
            "args": args,
            "returncode": proc.returncode,
            "stdout_tail": _tail_text(proc.stdout),
            "stderr_tail": _tail_text(proc.stderr),
            "timed_out": False,
            "duration_seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "returncode": None,
            "stdout_tail": _tail_text(exc.stdout),
            "stderr_tail": _tail_text(exc.stderr),
            "timed_out": True,
            "duration_seconds": round(time.time() - started, 3),
        }


def probe_repo(repo_path: Path, timeout: float = 15.0, include_fsck: bool = False) -> dict[str, Any]:
    checks = [
        run_git(repo_path, ["rev-parse", "--is-inside-work-tree"], timeout),
        run_git(repo_path, ["status", "--short", "--untracked-files=no"], timeout),
    ]
    if include_fsck:
        checks.append(run_git(repo_path, ["fsck", "--connectivity-only"], timeout))

    combined_output = "\n".join(
        f"{check['stdout_tail']}\n{check['stderr_tail']}" for check in checks
    )
    corruption_class = classify_git_output(combined_output)
    timed_out = any(check["timed_out"] for check in checks)
    commands_ok = all(check["returncode"] == 0 and not check["timed_out"] for check in checks)
    failure_class = corruption_class
    if failure_class is None and timed_out:
        failure_class = "git_repo_health_probe_timeout"
    elif failure_class is None and not commands_ok:
        failure_class = "git_repo_unusable"

    ok = commands_ok and corruption_class is None
    return {
        "checked_at": iso_now(),
        "repo_path": str(repo_path),
        "ok": ok,
        "failure_detected": not ok,
        "failure_class": failure_class,
        "corruption_detected": corruption_class is not None,
        "corruption_class": corruption_class,
        "timed_out": timed_out,
        "destructive_action_taken": False,
        "recommended_action": (
            "do_not_reuse_checkout_fresh_clone_recommended" if failure_class else "repo_healthy"
        ),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only RustChain checkout health probe for local developer/agent clones."
    )
    parser.add_argument("--repo-path", type=Path, default=Path.cwd())
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--fsck",
        action="store_true",
        help="Also run git fsck --connectivity-only. This is still read-only but can be slower.",
    )
    args = parser.parse_args()

    report = probe_repo(args.repo_path, timeout=args.timeout, include_fsck=args.fsck)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
