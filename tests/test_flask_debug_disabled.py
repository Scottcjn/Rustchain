import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_FLASK_ENTRYPOINTS = [
    ROOT / "bcos_directory.py",
    ROOT / "bridge" / "bridge_api.py",
    ROOT / "contributor_registry.py",
    ROOT / "explorer" / "app.py",
    ROOT / "faucet_service" / "faucet_service.py",
    ROOT / "keeper_explorer.py",
    ROOT / "security_test_payment_widget.py",
]


def is_debug_subscript(node):
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "debug"
    )


def debug_true_locations(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    locations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (
                    keyword.arg == "debug"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    locations.append((node.lineno, "app.run debug=True"))

        if isinstance(node, ast.Assign):
            assigns_true = isinstance(node.value, ast.Constant) and node.value.value is True
            if assigns_true and any(is_debug_subscript(target) for target in node.targets):
                locations.append((node.lineno, "debug config assignment to True"))

    return locations


def test_public_flask_entrypoints_do_not_enable_debug_mode():
    failures = {
        str(path.relative_to(ROOT)): debug_true_locations(path)
        for path in PUBLIC_FLASK_ENTRYPOINTS
    }
    failures = {path: locations for path, locations in failures.items() if locations}

    assert failures == {}
