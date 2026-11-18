#!/usr/bin/env python3
"""Unit tests for tools/check_relative_links.py and README/doc link integrity (Bounty #16248)."""

import tempfile
from pathlib import Path
from tools.check_relative_links import check_file, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_top_level_docs_have_zero_broken_relative_links():
    """README.md, BCOS.md, CONSULTING.md, CPU_ANTIQUITY_SYSTEM.md, and INSTALL.md must have 0 broken relative links."""
    for doc_name in ("README.md", "BCOS.md", "CONSULTING.md", "CPU_ANTIQUITY_SYSTEM.md", "INSTALL.md"):
        doc_path = REPO_ROOT / doc_name
        if doc_path.exists():
            broken = check_file(str(doc_path), str(REPO_ROOT))
            assert broken == [], f"Broken relative links in {doc_name}: {broken}"


def test_readme_faq_and_tokenomics_links_point_to_existing_docs():
    """Verify #7910, #7908, #7886, #7885, #7792 links resolve to existing repo docs."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "[FAQ](docs/FAQ.md)" in readme
    assert "https://rustchain.org/faq" not in readme
    assert "https://rustchain.org/api/tokenomics" not in readme
    assert "docs/WHITEPAPER.md" in readme
    assert "BCOS.md" in readme


def test_check_relative_links_fails_on_broken_relative_link():
    """Demonstrate that introducing a broken relative link causes check_relative_links.py to exit non-zero."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "existing.md").write_text("# Existing\n", encoding="utf-8")
        good_doc = root / "GOOD.md"
        good_doc.write_text("See [valid](existing.md) and `[ignored_in_code](missing.md)`.\n", encoding="utf-8")
        assert check_file(str(good_doc), str(root)) == []
        assert main(["--root", str(root), "GOOD.md"]) == 0

        bad_doc = root / "BAD.md"
        bad_doc.write_text("See [dead link](docs/does_not_exist_16248.md).\n", encoding="utf-8")
        broken = check_file(str(bad_doc), str(root))
        assert len(broken) == 1
        assert broken[0][3] == "docs/does_not_exist_16248.md"
        assert main(["--root", str(root), "BAD.md"]) == 1
