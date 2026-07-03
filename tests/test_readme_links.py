"""Regression tests for README.md relative documentation links.

Covers: https://github.com/Scottcjn/Rustchain/issues/7792
Verifies that every relative link in README.md points to a file that
actually exists in the repository, preventing broken documentation
links from being merged.
"""

import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")


@pytest.fixture(scope="module")
def readme_content():
    with open(README_PATH, encoding="utf-8") as f:
        return f.read()


def _extract_relative_links(content: str) -> list[str]:
    """Extract all relative (non-HTTP) markdown links from content."""
    links = []
    for match in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', content):
        url = match.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            continue
        if url.startswith("#"):
            continue
        if url.startswith("mailto:"):
            continue
        links.append(url.split("#")[0])
    return links


class TestREADMELinks:
    def test_all_relative_links_resolve(self, readme_content):
        """Every relative link in README.md must point to an existing file or directory.

        Regression test for: https://github.com/Scottcjn/Rustchain/issues/7792
        """
        links = _extract_relative_links(readme_content)
        broken = []
        for link in links:
            path = os.path.join(REPO_ROOT, link)
            if not os.path.exists(path):
                broken.append(link)
        assert not broken, (
            f"README.md contains {len(broken)} broken relative link(s):\n"
            + "\n".join(f"  - {link}" for link in broken)
        )

    def test_no_references_to_removed_sprint_docs(self, readme_content):
        """Verify links to removed sprint documentation are gone.

        These files were removed but links lingered:
        - docs/attestation-pipeline.md (use docs/attestation-flow.md)
        - docs/pay-out-ledger.md (use docs/epoch-settlement.md)
        - docs/sprint/HN_ANNOUNCEMENT.md
        - docs/sprint/REDDIT_DEPIN.md
        - docs/sprint/LOBSTERS_THREAD.md
        """
        removed_targets = [
            "docs/attestation-pipeline.md",
            "docs/pay-out-ledger.md",
            "docs/sprint/HN_ANNOUNCEMENT.md",
            "docs/sprint/REDDIT_DEPIN.md",
            "docs/sprint/LOBSTERS_THREAD.md",
        ]
        for target in removed_targets:
            assert target not in readme_content, (
                f"README.md still references removed file: {target}"
            )
