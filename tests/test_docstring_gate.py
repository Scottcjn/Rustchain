#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for scripts/docstring_gate.py.

The check that carries the weight is `count_added_docstrings`: without it, a
claim saying "I added 40 docstrings" would pay out for 40 added lines of
anything at all. These pin that it counts docstrings and nothing else.
"""
import importlib.util
import os
import unittest
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "dummy")
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "docstring_gate.py"
spec = importlib.util.spec_from_file_location("docstring_gate_under_test", SCRIPT)
dg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dg)


def diff(*added_lines, path="a/x.py"):
    head = f"diff --git {path} b/{path.split('a/')[-1]}\n--- {path}\n+++ b/{path.split('a/')[-1]}\n@@ -1 +1 @@\n"
    return head + "\n".join(added_lines)


class CountingTests(unittest.TestCase):
    def test_counts_one_line_docstrings(self):
        d = diff('+    """Return the name."""', '+    """Do a thing."""')
        self.assertEqual(dg.count_added_docstrings(d)[0], 2)

    def test_multiline_docstring_counts_once(self):
        d = diff('+    """Summary line.', '+', '+    More detail here.', '+    """')
        doc, total, _ = dg.count_added_docstrings(d)
        self.assertEqual(doc, 1, "a multi-line docstring is one unit, not four")
        self.assertEqual(total, 4)

    def test_plain_code_is_not_a_docstring(self):
        d = diff('+x = 1', '+def f():', '+    return 2')
        self.assertEqual(dg.count_added_docstrings(d)[0], 0)

    def test_comments_are_not_docstrings(self):
        d = diff('+# this is a comment', '+    # another one')
        self.assertEqual(dg.count_added_docstrings(d)[0], 0)

    def test_string_assignment_is_not_a_docstring(self):
        """The abuse case: padding a diff with triple-quoted values."""
        d = diff('+SQL = """SELECT 1"""', '+    """A real docstring."""')
        # SQL = """...""" does not OPEN at line start, so only the real one counts.
        self.assertEqual(dg.count_added_docstrings(d)[0], 1)

    def test_single_quote_docstrings(self):
        d = diff("+    '''Alt quoting style.'''")
        self.assertEqual(dg.count_added_docstrings(d)[0], 1)

    def test_removed_lines_do_not_count(self):
        d = diff('+    """Kept."""', '-    """Deleted."""')
        self.assertEqual(dg.count_added_docstrings(d)[0], 1)

    def test_files_are_collected(self):
        d = diff('+    """Doc."""', path="a/generation/provider.py")
        self.assertIn("generation/provider.py", dg.count_added_docstrings(d)[2])

    def test_raw_and_unicode_prefixes(self):
        d = diff('+    r"""Raw docstring."""', '+    u"""Unicode docstring."""')
        self.assertEqual(dg.count_added_docstrings(d)[0], 2)

    def test_fstring_prefixed_strings_are_not_docstrings(self):
        """f- and rf-prefixed strings are valid Python but not docstrings."""
        d = diff('+    f"""F-string expression."""', '+    rf"""Raw f-string expression."""')
        self.assertEqual(dg.count_added_docstrings(d)[0], 0)


class ClaimParsingTests(unittest.TestCase):
    def test_recognises_docstring_claims(self):
        self.assertTrue(dg.is_docstring_claim("Claim: docs batch 49 - provider.py docstrings", ""))
        self.assertTrue(dg.is_docstring_claim("Bounty claim: BoTTube docstring PR #1683", ""))

    def test_ignores_review_claims(self):
        self.assertFalse(dg.is_docstring_claim("[Bounty Claim] PR Review - RustChain PR #5395", ""))

    def test_pr_url_extraction(self):
        m = dg.PR_RE.search("PR: https://github.com/Scottcjn/bottube/pull/1696")
        self.assertEqual((m.group(1), m.group(2)), ("Scottcjn/bottube", "1696"))

    def test_count_extraction(self):
        for text, want in [
            ("Functions documented: 7 (get_name, ...)", "7"),
            ("Added docstrings to 5 undocumented methods", "5"),
        ]:
            m = dg.COUNT_RE.search(text)
            self.assertIsNotNone(m, text)
            self.assertEqual(m.group(1), want)


class WeeklyCeilingTests(unittest.TestCase):
    """The per-claim ceiling bounds nothing: batches are ~5 RTC each, so the
    50th one passes just as easily as the 1st. The weekly ceiling is the one
    that actually bounds an unbounded bounty type."""

    def setUp(self):
        self._gh = dg.gh

    def tearDown(self):
        dg.gh = self._gh

    def _with_prior(self, amounts):
        """Fake N prior verified claims carrying these payout markers."""
        items = [{"number": 900 + i, "body": ""} for i in range(len(amounts))]

        def fake(args, default=None, strict=False):
            joined = " ".join(args)
            if "search/issues" in joined:
                return {"items": items}
            if "/comments" in joined:
                idx = int(joined.split("/issues/")[1].split("/")[0]) - 900
                return [{"user": {"login": "github-actions[bot]"},
                         "body": f"<!-- rtc-payout-amount: {amounts[idx]} -->"}]
            return default
        dg.gh = fake

    def test_sums_prior_week(self):
        self._with_prior([5.0, 7.5, 6.0])
        self.assertEqual(dg.docstring_rtc_this_week("someone"), 18.5)

    def test_no_prior_claims_is_zero(self):
        self._with_prior([])
        self.assertEqual(dg.docstring_rtc_this_week("someone"), 0.0)

    def test_ceiling_is_higher_than_typical_top_earner(self):
        """Measured 2026-08-10: top contributors earn 20-50 RTC/week across ALL
        bounty types. A docstring-only ceiling below that would be punitive."""
        self.assertGreaterEqual(dg.MAX_RTC_PER_WEEK, 40)

    def test_per_claim_ceiling_alone_would_not_bound_volume(self):
        """Documents why the weekly cap exists: a typical batch is far under
        the per-claim ceiling, so volume is unbounded without it."""
        typical_batch_rtc = 10 * dg.RATE     # 10 functions
        self.assertLess(typical_batch_rtc, dg.MAX_RTC)


class UntrustedMarkerTests(unittest.TestCase):
    """Bounty #16471, reported by @fsalmon1991 (2026-09-22).

    `docstring_rtc_this_week()` summed the FIRST `rtc-payout-amount` marker on
    each prior claim with no author check. Issue comments are public input, so
    anyone could front-run the gate's marker: a large value made an honest
    contributor look over the weekly cap (held work), and a `0` undercounted
    prior earnings so the cap failed OPEN. Only markers from the identities the
    gate/payout actually post as may count; everything else is ignored.
    """

    BOT = "github-actions[bot]"

    def setUp(self):
        self._gh = dg.gh

    def tearDown(self):
        dg.gh = self._gh

    def _one_claim(self, comments):
        def fake(args, default=None, strict=False):
            joined = " ".join(args)
            if "search/issues" in joined:
                return {"items": [{"number": 901, "body": ""}]}
            if "/comments" in joined:
                return comments
            return default
        dg.gh = fake

    @staticmethod
    def _c(login, amount):
        return {"user": {"login": login}, "body": f"<!-- rtc-payout-amount: {amount} -->"}

    def test_spoofed_marker_alone_does_not_count(self):
        self._one_claim([self._c("random-user", 40)])
        with self.assertRaises(dg.GhError):
            dg.docstring_rtc_this_week("victim")

    def test_genuine_bot_marker_counts(self):
        self._one_claim([self._c(self.BOT, 5)])
        self.assertEqual(dg.docstring_rtc_this_week("someone"), 5.0)

    def test_inflating_marker_before_gate_marker_is_ignored(self):
        """Front-run with 40: must not push an honest contributor over the cap."""
        self._one_claim([self._c("attacker", 40), self._c(self.BOT, 5)])
        self.assertEqual(dg.docstring_rtc_this_week("victim"), 5.0)

    def test_zero_marker_before_gate_marker_is_ignored(self):
        """Front-run with 0: must not undercount prior earnings (cap fail-open)."""
        self._one_claim([self._c("collaborator", 0), self._c(self.BOT, 5)])
        self.assertEqual(dg.docstring_rtc_this_week("farmer"), 5.0)

    def test_marker_after_gate_marker_is_ignored(self):
        self._one_claim([self._c(self.BOT, 5), self._c("attacker", 0)])
        self.assertEqual(dg.docstring_rtc_this_week("farmer"), 5.0)

    def test_lookalike_and_missing_author_are_untrusted(self):
        self._one_claim([self._c("github-actions-bot", 9), self._c("scottcjn-fan", 9),
                         {"body": "<!-- rtc-payout-amount: 9 -->"},
                         {"user": None, "body": "<!-- rtc-payout-amount: 9 -->"}])
        with self.assertRaises(dg.GhError):
            dg.docstring_rtc_this_week("someone")

    def test_maintainer_marker_counts_and_graphql_shape_is_read(self):
        self._one_claim([{"author": {"login": "Scottcjn"},
                          "body": "<!-- rtc-payout-amount: 3 -->"}])
        self.assertEqual(dg.docstring_rtc_this_week("someone"), 3.0)

    def test_unparseable_trusted_marker_is_skipped_not_a_crash(self):
        """`[\\d.]+` matches `...` and `1.2.3`; those used to reach float() and
        raise ValueError, which main() does not catch, killing the gate run."""
        for bad in ("...", "1.2.3", "."):
            self._one_claim([self._c(self.BOT, 5), self._c(self.BOT, bad)])
            self.assertEqual(dg.docstring_rtc_this_week("someone"), 5.0, bad)
            self._one_claim([self._c(self.BOT, bad)])
            with self.assertRaises(dg.GhError):
                dg.docstring_rtc_this_week("someone")

    def test_author_key_wins_over_user_key_like_the_payout_runner(self):
        c = {"author": {"login": "attacker"}, "user": {"login": self.BOT},
             "body": "<!-- rtc-payout-amount: 9 -->"}
        self._one_claim([c])
        with self.assertRaises(dg.GhError):
            dg.docstring_rtc_this_week("someone")

    def test_last_trusted_marker_wins_like_the_payout_runner(self):
        """bounty_payout.py pays the LAST trusted marker; the cap must count the
        same figure the payout will actually move, not a different one."""
        self._one_claim([self._c(self.BOT, 5), self._c("Scottcjn", 2.5)])
        self.assertEqual(dg.docstring_rtc_this_week("someone"), 2.5)




class PaginationAndFailClosedTests(unittest.TestCase):
    """Bounty #17054: weekly-cap lookup must paginate both search/issues and
    issue comments (`--paginate --slurp`), and fail closed (`GhError`) when a
    `docstring-verified` prior claim has no trusted marker."""

    BOT = "github-actions[bot]"

    def setUp(self):
        self._gh = dg.gh

    def tearDown(self):
        dg.gh = self._gh

    def test_150_comments_with_trusted_marker_at_position_120_is_counted(self):
        """Regression test (#17054): 150 comments where 119 noise comments precede
        the gate's trusted marker at position 120 (page 2 of a 100-per-page fetch)."""
        all_comments = [
            {"user": {"login": f"spammer-{i}"}, "body": f"noise comment #{i}"}
            for i in range(1, 151)
        ]
        # Place the trusted marker at 1-based position 120 (0-based index 119, on page 2)
        all_comments[119] = {
            "user": {"login": self.BOT},
            "body": "Verified!\n<!-- rtc-payout-amount: 12.5 -->",
        }
        page1 = all_comments[:100]
        page2 = all_comments[100:]
        recorded_calls = []

        def fake_gh(args, default=None, strict=False):
            recorded_calls.append(list(args))
            joined = " ".join(args)
            self.assertIn("--paginate", args, f"Expected --paginate in {args}")
            self.assertIn("--slurp", args, f"Expected --slurp in {args}")
            if "search/issues" in joined:
                return [{"items": [{"number": 1001, "body": ""}]}]
            if "/issues/1001/comments" in joined:
                return [page1, page2]
            return default

        dg.gh = fake_gh
        self.assertEqual(dg.docstring_rtc_this_week("contributor"), 12.5)
        self.assertEqual(len(recorded_calls), 2)

    def test_multipage_search_issues_sums_across_all_pages(self):
        """More than 100 prior claims in a week (2 slurped search pages) are all summed."""
        page1_items = [{"number": 2000 + i} for i in range(100)]
        page2_items = [{"number": 2100 + i} for i in range(5)]

        def fake_gh(args, default=None, strict=False):
            joined = " ".join(args)
            if "search/issues" in joined:
                return [{"items": page1_items}, {"items": page2_items}]
            if "/comments" in joined:
                return [[{"user": {"login": self.BOT}, "body": "<!-- rtc-payout-amount: 0.5 -->"}]]
            return default

        dg.gh = fake_gh
        self.assertEqual(dg.docstring_rtc_this_week("prolific-author"), 52.5)

    def test_docstring_verified_claim_without_trusted_marker_fails_closed(self):
        """A `docstring-verified` prior claim with no trusted marker is 'unknown', not 0,
        and must raise GhError so main() holds the new claim for `needs-human`."""
        def fake_gh(args, default=None, strict=False):
            joined = " ".join(args)
            if "search/issues" in joined:
                return [{"items": [{"number": 3001}]}]
            if "/issues/3001/comments" in joined:
                return [[{"user": {"login": "some-user"}, "body": "no marker here"}]]
            return default

        dg.gh = fake_gh
        with self.assertRaises(dg.GhError):
            dg.docstring_rtc_this_week("someone")


if __name__ == "__main__":
    unittest.main()
