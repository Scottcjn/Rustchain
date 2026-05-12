# SPDX-License-Identifier: MIT
import py_compile
from pathlib import Path


def test_deprecated_v3_fingerprint_miner_compiles():
    repo_root = Path(__file__).resolve().parents[1]
    py_compile.compile(
        str(repo_root / "deprecated" / "old_miners" / "rustchain_miner_v3_fingerprint.py"),
        doraise=True,
    )
