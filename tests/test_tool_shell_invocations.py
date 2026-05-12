# SPDX-License-Identifier: MIT

import ast
from pathlib import Path


TOOL_FILES = [
    Path("tools/gpu_display_detector.py"),
    Path("tools/os_detector.py"),
]


def test_tool_detectors_do_not_use_shell_true():
    for path in TOOL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            for keyword in call.keywords:
                assert not (
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ), f"{path} must not invoke subprocesses through a shell"
