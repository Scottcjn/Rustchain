# SPDX-License-Identifier: MIT

from __future__ import annotations

from tools import bcos_spdx_check


def test_has_spdx_accepts_header_after_shebang():
    lines = [
        "#!/usr/bin/env python3",
        "# SPDX-License-Identifier: Apache-2.0",
        "print('hello')",
    ]

    assert bcos_spdx_check._has_spdx(lines) is True


def test_has_spdx_rejects_header_outside_top_scan_window():
    lines = ["# ordinary comment"] * 20
    lines.append("# SPDX-License-Identifier: MIT")

    assert bcos_spdx_check._has_spdx(lines) is False


def test_top_lines_limits_reads_and_strips_newlines(tmp_path):
    source = tmp_path / "script.py"
    source.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    assert bcos_spdx_check._top_lines(source, max_lines=3) == ["one", "two", "three"]


def test_top_lines_returns_empty_list_for_missing_file(tmp_path):
    assert bcos_spdx_check._top_lines(tmp_path / "missing.py") == []


def test_git_diff_name_status_parses_valid_rows(monkeypatch):
    def fake_run(cmd):
        assert cmd == ["git", "diff", "--name-status", "origin/main...HEAD"]
        return "A\tnew.py\nmalformed row\nM\t tools/old.py \nR100\told.py\tnew.py\n"

    monkeypatch.setattr(bcos_spdx_check, "_run", fake_run)

    assert bcos_spdx_check._git_diff_name_status("origin/main") == [
        ("A", "new.py"),
        ("M", "tools/old.py"),
        ("R100", "old.py\tnew.py"),
    ]


def test_ensure_base_ref_returns_existing_ref(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        return ""

    monkeypatch.setattr(bcos_spdx_check, "_run", fake_run)

    assert bcos_spdx_check._ensure_base_ref("origin/main") == "origin/main"
    assert calls == [["git", "rev-parse", "--verify", "origin/main"]]


def test_ensure_base_ref_fetches_remote_branch_when_missing(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        if cmd == ["git", "rev-parse", "--verify", "upstream/main"]:
            raise RuntimeError("missing")
        return ""

    monkeypatch.setattr(bcos_spdx_check, "_run", fake_run)

    assert bcos_spdx_check._ensure_base_ref("upstream/main") == "upstream/main"
    assert calls == [
        ["git", "rev-parse", "--verify", "upstream/main"],
        ["git", "fetch", "upstream", "main", "--depth=1"],
    ]


def test_ensure_base_ref_normalizes_missing_bare_branch(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        if cmd == ["git", "rev-parse", "--verify", "main"]:
            raise RuntimeError("missing")
        return ""

    monkeypatch.setattr(bcos_spdx_check, "_run", fake_run)

    assert bcos_spdx_check._ensure_base_ref("main") == "origin/main"
    assert calls == [
        ["git", "rev-parse", "--verify", "main"],
        ["git", "fetch", "origin", "main", "--depth=1"],
    ]
