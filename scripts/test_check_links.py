# SPDX-License-Identifier: MIT
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import check_links


def make_tree(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Setup Guide\n## Install Steps\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[guide](docs/guide.md)\n"
        "[install](docs/guide.md#install-steps)\n"
        "[top](#readme)\n"
        "# README\n"
        "[def-style][d]\n"
        "[d]: docs/guide.md\n",
        encoding="utf-8",
    )
    return tmp_path


def test_clean_tree_passes(tmp_path):
    root = make_tree(tmp_path)
    assert check_links.check_tree(root) == []
    assert check_links.main(["check_links.py", str(root)]) == 0


def test_missing_file_detected(tmp_path):
    root = make_tree(tmp_path)
    (root / "README.md").write_text("[gone](docs/nope.md)\n", encoding="utf-8")
    issues = check_links.check_tree(root)
    assert len(issues) == 1 and "file not found" in issues[0]
    assert check_links.main(["check_links.py", str(root)]) == 1


def test_missing_anchor_detected(tmp_path):
    root = make_tree(tmp_path)
    (root / "README.md").write_text("[x](docs/guide.md#not-there)\n[y](docs/guide.md#install-steps)\n", encoding="utf-8")
    issues = check_links.check_tree(root)
    assert len(issues) == 1 and "missing anchor" in issues[0]


def test_fenced_code_and_templates_ignored(tmp_path):
    root = make_tree(tmp_path)
    (root / "README.md").write_text(
        "```\n[fake](./does-not-exist.md)\n```\n[tpl]({{BASE_URL}}/x)\n", encoding="utf-8"
    )
    assert check_links.check_tree(root) == []


def test_vs16_percent_encoded_anchor(tmp_path):
    # GitHub keeps U+FE0F in slugs: '## ⚙️ Configuration' -> anchor '\uFE0F-configuration';
    # links must percent-encode it and the checker must decode fragments.
    (tmp_path / "README.md").write_text(
        "[cfg](#%EF%B8%8F-configuration)\n## ⚙️ Configuration\n", encoding="utf-8"
    )
    assert check_links.check_tree(tmp_path) == []
