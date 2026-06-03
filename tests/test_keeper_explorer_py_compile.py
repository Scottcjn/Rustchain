# SPDX-License-Identifier: MIT

import py_compile
import warnings
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KEEPER_EXPLORER_PATH = PROJECT_ROOT / "keeper_explorer.py"


def test_keeper_explorer_compiles_with_syntax_warnings_as_errors():
    """The embedded ASCII template should not trigger invalid escape warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        py_compile.compile(str(KEEPER_EXPLORER_PATH), doraise=True)
