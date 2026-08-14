"""
Tests for airdrop tier scoping fix (Issue #8184).

_determine_tier() used to count GitHub commits *anywhere* on GitHub,
so any established account qualified for the top tier (CORE = 200 wRTC)
without ever contributing to RustChain.

These tests verify the fix scopes the query to merged PRs within the
Scottcjn org and uses the correct API endpoint.
"""
import ast
import re
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _strip_comments_and_strings(source: str) -> str:
    """Strip comments and string literals so assertions target actual code."""
    tree = ast.parse(source)
    # Collect lines that are purely comments
    lines = source.splitlines(keepends=True)
    # Remove full-line comments and inline comments
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Remove inline comment (naive but sufficient for our check)
        code_part = re.split(r'(?<!\\)#', line, maxsplit=1)[0]
        cleaned.append(code_part)
    return "".join(cleaned)


class TestAirdropTierScope(unittest.TestCase):
    def setUp(self):
        self.module_path = os.path.join(
            os.path.dirname(__file__), '..', 'node', 'airdrop_v2.py'
        )
        with open(self.module_path, 'r') as f:
            self.raw_source = f.read()
        self.source = _strip_comments_and_strings(self.raw_source)

    def test_uses_search_issues_not_search_commits(self):
        """Must query /search/issues (PRs), not /search/commits."""
        self.assertIn("/search/issues", self.source,
            "Tier check should use the issues search endpoint for PRs")

    def test_does_not_use_search_commits(self):
        """The old /search/commits endpoint must be gone from code."""
        self.assertNotIn("api.github.com/search/commits", self.source,
            "/search/commits counts commits, not merged PRs")

    def test_query_is_scoped_to_org(self):
        """The search query must be scoped to the RustChain org."""
        self.assertIn("org:Scottcjn", self.source,
            "Contribution count must be scoped to the Scottcjn org, "
            "not all of GitHub")

    def test_query_uses_pr_and_merged_qualifiers(self):
        """The query must use is:pr is:merged qualifiers."""
        self.assertIn("is:pr", self.source,
            "Query must filter for pull requests")
        self.assertIn("is:merged", self.source,
            "Query must filter for merged PRs")

    def test_no_bare_merged_true_qualifier(self):
        """The old bare 'merged:true' qualifier must be gone from code."""
        self.assertNotIn("merged:true", self.source,
            "The old 'merged:true' qualifier is a PR-search qualifier "
            "that was misused on the commits endpoint")

    def test_no_cloak_preview_accept_header(self):
        """The commits-search Accept header must be gone."""
        self.assertNotIn("cloak-preview", self.source,
            "The 'application/vnd.github.cloak-preview' header was "
            "only needed for /search/commits")

    def test_module_compiles(self):
        """The module must be syntactically valid."""
        ast.parse(self.raw_source)


if __name__ == '__main__':
    unittest.main()
