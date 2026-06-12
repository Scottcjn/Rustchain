#!/usr/bin/env python3
"""Validate hashes embedded in rustchain_miner_setup.bat."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / "rustchain_miner_setup.bat"

EXPECTED_FILES = {
    "MINER_SHA256": ROOT / "rustchain_windows_miner.py",
    "CRYPTO_SHA256": ROOT / "miner_crypto.py",
}


def read_bootstrap_hashes() -> dict[str, str]:
    content = BOOTSTRAP.read_text(encoding="utf-8")
    hashes: dict[str, str] = {}
    for name in EXPECTED_FILES:
        match = re.search(rf'^set "{name}=([0-9a-fA-F]{{64}})"$', content, re.MULTILINE)
        if not match:
            raise ValueError(f"{BOOTSTRAP.name} is missing {name}")
        hashes[name] = match.group(1).lower()
    return hashes


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures: list[str] = []
    bootstrap_hashes = read_bootstrap_hashes()

    for name, path in EXPECTED_FILES.items():
        actual = sha256(path)
        expected = bootstrap_hashes[name]
        if actual != expected:
            failures.append(f"{name}: expected {expected}, actual {actual} ({path.name})")

    if failures:
        print("Windows bootstrap hash check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("Windows bootstrap hashes are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
