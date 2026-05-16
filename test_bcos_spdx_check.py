# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "tools" / "bcos_spdx_check.py"
SPEC = importlib.util.spec_from_file_location("bcos_spdx_check", MODULE_PATH)
bcos_spdx_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bcos_spdx_check)


def test_top_lines_reads_only_requested_prefix(tmp_path):
    path = tmp_path / "script.py"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert bcos_spdx_check._top_lines(path, max_lines=2) == ["one", "two"]


def test_top_lines_returns_empty_list_for_unreadable_path(tmp_path):
    assert bcos_spdx_check._top_lines(tmp_path / "missing.py") == []


def test_has_spdx_accepts_identifier_near_top_after_shebang():
    lines = [
        "#!/usr/bin/env python3",
        "# SPDX-License-Identifier: MIT",
        "",
        "print('ok')",
    ]

    assert bcos_spdx_check._has_spdx(lines) is True


def test_has_spdx_rejects_empty_or_late_identifier():
    late_header = ["# comment"] * 21 + ["# SPDX-License-Identifier: MIT"]

    assert bcos_spdx_check._has_spdx([]) is False
    assert bcos_spdx_check._has_spdx(late_header) is False


def test_has_spdx_accepts_common_license_expression_characters():
    assert bcos_spdx_check._has_spdx(
        ["// SPDX-License-Identifier: Apache-2.0+MIT"]
    ) is True
