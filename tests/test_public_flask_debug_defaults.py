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


def _literal_value(node):
    return node.value if isinstance(node, ast.Constant) else None


def _kw(call, name):
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def test_public_flask_entrypoints_do_not_enable_debug_by_default():
    offenders = []

    for path in PUBLIC_FLASK_ENTRYPOINTS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "run":
                continue

            host_node = _kw(node, "host")
            debug_node = _kw(node, "debug")
            host = _literal_value(host_node) if host_node else None
            debug = _literal_value(debug_node) if debug_node else None

            if host == "0.0.0.0" and debug is True:
                offenders.append(f"{path}:{node.lineno}")

    assert offenders == []
