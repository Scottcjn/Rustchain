# SPDX-License-Identifier: MIT
import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DETECTOR_PATHS = [
    REPO_ROOT / "tools" / "gpu_display_detector.py",
    REPO_ROOT / "tools" / "os_detector.py",
]


def _shell_true_locations(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    locations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                locations.append(node.lineno)
    return locations


def test_detector_tools_do_not_use_shell_true():
    offenders = {
        path.relative_to(REPO_ROOT).as_posix(): _shell_true_locations(path)
        for path in DETECTOR_PATHS
    }

    assert offenders == {
        "tools/gpu_display_detector.py": [],
        "tools/os_detector.py": [],
    }
