import ast
from pathlib import Path


PUBLIC_FLASK_ENTRYPOINTS = [
    "bcos_directory.py",
    "bridge/bridge_api.py",
    "contributor_registry.py",
    "explorer/app.py",
    "keeper_explorer.py",
    "security_test_payment_widget.py",
]


def _literal_keyword(call: ast.Call, keyword_name: str):
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value
    return None


def _is_app_run(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "run"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "app"
    )


def test_public_flask_entrypoints_do_not_hardcode_debug_true():
    repo_root = Path(__file__).resolve().parents[1]

    for relative_path in PUBLIC_FLASK_ENTRYPOINTS:
        source_path = repo_root / relative_path
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_app_run(node):
                continue

            host = _literal_keyword(node, "host")
            debug = _literal_keyword(node, "debug")

            binds_public_interface = isinstance(host, ast.Constant) and host.value == "0.0.0.0"
            hardcodes_debug_true = isinstance(debug, ast.Constant) and debug.value is True

            assert not (
                binds_public_interface and hardcodes_debug_true
            ), f"{relative_path} binds 0.0.0.0 with debug=True"
