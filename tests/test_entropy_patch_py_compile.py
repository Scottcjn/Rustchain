# SPDX-License-Identifier: MIT
import py_compile
from pathlib import Path


def test_entropy_enforcement_patch_compiles():
    repo_root = Path(__file__).resolve().parents[1]
    py_compile.compile(
        str(
            repo_root
            / "deprecated"
            / "patches"
            / "rustchain_entropy_enforcement_patch.py"
        ),
        doraise=True,
    )
