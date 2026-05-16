# SPDX-License-Identifier: MIT

import py_compile
import warnings
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = PROJECT_ROOT / "tools" / "bounty-bot-pro" / "verifier.py"


def test_bounty_verifier_compiles_with_syntax_warnings_as_errors():
    """Invalid escape sequences should not break strict bytecode compilation."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        py_compile.compile(str(VERIFIER_PATH), doraise=True)
