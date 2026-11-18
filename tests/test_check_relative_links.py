# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_CHECKER_PATH = REPO_ROOT / "tools" / "check_relative_links.py"


def _load_link_checker():
    spec = importlib.util.spec_from_file_location("link_checker_under_test", LINK_CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_link_checker()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _broken(tmp_path: Path, text: str) -> list:
    """Links of one README-style file, checked with tmp_path as the repo root."""
    page = _write(tmp_path / "docs" / "README.md", text)
    return checker.check_file(str(page), str(tmp_path))


def test_resolves_relative_file_links_and_anchors(tmp_path):
    _write(tmp_path / "docs" / "mining.md", "# Mining\n\n## How It Works\n")
    assert _broken(tmp_path, "[Mining](mining.md) and [how](mining.md#how-it-works)\n") == []


def test_flags_missing_relative_file(tmp_path):
    broken = _broken(tmp_path, "[gone](nope.md)\n")
    assert len(broken) == 1
    assert "nope.md" in broken[0][2]


def test_flags_missing_heading_anchor(tmp_path):
    _write(tmp_path / "docs" / "mining.md", "# Mining\n")
    broken = _broken(tmp_path, "[deep](mining.md#not-a-heading)\n")
    assert len(broken) == 1
    assert "no such heading" in broken[0][2]


def test_numbered_heading_slug_matches_github_rules(tmp_path):
    _write(tmp_path / "docs" / "api.md", "# API\n\n## 1. Network & Status\n")
    assert checker.slug("1. Network & Status") == "1-network--status"
    assert _broken(tmp_path, "[status](api.md#1-network--status)\n") == []


def test_flags_missing_same_file_anchor(tmp_path):
    assert len(_broken(tmp_path, "# Title\n\n[jump](#missing-section)\n")) == 1
    assert _broken(tmp_path, "# Title\n\n## Real Section\n\n[jump](#real-section)\n") == []


def test_html_href_and_img_src_are_checked(tmp_path):
    _write(tmp_path / "docs" / "guide.md", "# Guide\n")
    broken = _broken(tmp_path, '<a href="guide.md">g</a> <img src="pic.png">\n')
    assert len(broken) == 1 and "pic.png" in broken[0][2]
    assert _broken(tmp_path, '<a href="guide.md">g</a>\n') == []


def test_external_urls_and_code_samples_are_ignored(tmp_path):
    text = ("[site](https://rustchain.org/bcos/) and [mail](mailto:a@b.c)\n"
            "```\n[example](./missing-in-code-block.md)\n```\n"
            "Inline `[not-a-link](also-missing.md)` stays text\n")
    assert _broken(tmp_path, text) == []


def test_repository_docs_have_no_broken_relative_links():
    """The gate CI runs (ci.yml -> 'Verify relative documentation links')."""
    broken = []
    for root, dirs, files in os.walk(str(REPO_ROOT)):
        dirs[:] = [d for d in dirs if d not in (".git", "venv", ".venv", "node_modules", "__pycache__")]
        for name in files:
            if name.endswith(".md"):
                path = str(Path(root) / name)
                broken.extend(checker.check_file(path, str(REPO_ROOT)))
    assert broken == [], f"broken relative links: {broken[:10]}"
