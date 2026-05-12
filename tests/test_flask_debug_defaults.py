# SPDX-License-Identifier: MIT

import ast
from pathlib import Path


PUBLIC_FLASK_ENTRYPOINTS = [
    Path("bcos_directory.py"),
    Path("bridge/bridge_api.py"),
    Path("contributor_registry.py"),
    Path("explorer/app.py"),
    Path("keeper_explorer.py"),
    Path("security_test_payment_widget.py"),
]


def test_public_flask_entrypoints_do_not_force_debug_true():
    for path in PUBLIC_FLASK_ENTRYPOINTS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            if not isinstance(call.func, ast.Attribute) or call.func.attr != "run":
                continue

            debug_keywords = [kw for kw in call.keywords if kw.arg == "debug"]
            assert debug_keywords, f"{path} should pass debug explicitly"
            for keyword in debug_keywords:
                assert not (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ), f"{path} must not force Flask debug mode on"
