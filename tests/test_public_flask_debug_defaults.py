# SPDX-License-Identifier: MIT

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_FLASK_ENTRYPOINTS = [
    "bcos_directory.py",
    "bridge/bridge_api.py",
    "contributor_registry.py",
    "explorer/app.py",
    "keeper_explorer.py",
    "security_test_payment_widget.py",
]


def _const_keyword(call, name):
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def _is_public_flask_run(call):
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "run"
        and _const_keyword(call, "host") == "0.0.0.0"
    )


def test_public_flask_entrypoints_do_not_default_to_debug_true():
    violations = []

    for relative_path in PUBLIC_FLASK_ENTRYPOINTS:
        path = REPO_ROOT / relative_path
        tree = ast.parse(path.read_text(), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_public_flask_run(node):
                if _const_keyword(node, "debug") is True:
                    violations.append(f"{relative_path}:{node.lineno}")

    assert violations == []
