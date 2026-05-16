# SPDX-License-Identifier: MIT

import py_compile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_entropy_enforcement_patch_helper_byte_compiles():
    patch_helper = REPO_ROOT / "deprecated" / "patches" / "rustchain_entropy_enforcement_patch.py"

    py_compile.compile(str(patch_helper), doraise=True)
