#!/usr/bin/env python3
"""
Tests for Dynamic Shields Badge Generator v2 (Bounty #310)

Run:
    python -m pytest .github/scripts/test_generate_badges.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from generate_dynamic_badges import (
    badge,
    generate_category_badge,
    generate_hunter_badge,
    generate_network_status_badge,
    generate_top_hunters_badge,
    generate_total_bounties_badge,
    generate_weekly_growth_badge,
    generate_all_badges,
    make_slug,
    validate_badge,
    _parse_contributors,
)


# ── Slug tests ───────────────────────────────────────────────────────

class TestMakeSlug(unittest.TestCase):
    def test_simple_name(self):
        slug = make_slug("B1tor")
        self.assertTrue(slug.startswith("b1tor-"))
        self.assertEqual(len(slug.split("-")[-1]), 4)

    def test_special_chars(self):
        slug = make_slug("user@domain.com")
        self.assertNotIn("@", slug)
        self.assertNotIn(".", slug)

    def test_spaces(self):
        slug = make_slug("My Cool Name")
        self.assertNotIn(" ", slug)
        self.assertTrue(slug.startswith("my-cool-name-"))

    def test_empty(self):
        slug = make_slug("")
        self.assertTrue(slug.startswith("unknown-"))

    def test_collision_resistance(self):
        # Different names should produce different slugs
        s1 = make_slug("alice")
        s2 = make_slug("Alice")  # different case = different hash
        self.assertNotEqual(s1, s2)

    def test_deterministic(self):
        s1 = make_slug("test-user")
        s2 = make_slug("test-user")
        self.assertEqual(s1, s2)


# ── Badge template tests ────────────────────────────────────────────

class TestBadgeTemplate(unittest.TestCase):
    def test_basic_badge(self):
        b = badge("Test", "123")
        self.assertEqual(b["schemaVersion"], 1)
        self.assertEqual(b["label"], "Test")
        self.assertEqual(b["message"], "123")

    def test_custom_color(self):
        b = badge("Test", "ok", color="blue")
        self.assertEqual(b["color"], "blue")

    def test_message_is_string(self):
        b = badge("Test", 42)
        self.assertEqual(b["message"], "42")


# ── Badge validation tests ──────────────────────────────────────────

class TestValidation(unittest.TestCase):
    def test_valid_badge(self):
        b = badge("Label", "Message")
        self.assertEqual(validate_badge(b), [])

    def test_missing_label(self):
        b = badge("", "Message")
        errors = validate_badge(b)
        self.assertTrue(any("label" in e for e in errors))

    def test_wrong_schema_version(self):
        b = badge("L", "M")
        b["schemaVersion"] = 2
        errors = validate_badge(b)
        self.assertTrue(any("schemaVersion" in e for e in errors))

    def test_missing_message(self):
        b = {"schemaVersion": 1, "label": "Test", "color": "green"}
        errors = validate_badge(b)
        self.assertTrue(any("message" in e for e in errors))


# ── Network status badge ────────────────────────────────────────────

class TestNetworkStatusBadge(unittest.TestCase):
    def test_healthy(self):
        b = generate_network_status_badge({"network_status": "healthy"})
        self.assertEqual(b["message"], "Healthy")
        self.assertEqual(validate_badge(b), [])

    def test_degraded(self):
        b = generate_network_status_badge({"network_status": "degraded"})
        self.assertEqual(b["message"], "Degraded")

    def test_unknown(self):
        b = generate_network_status_badge({})
        self.assertEqual(b["message"], "Unknown")


# ── Total bounties badge ────────────────────────────────────────────

class TestTotalBountiesBadge(unittest.TestCase):
    def test_with_data(self):
        b = generate_total_bounties_badge({"total_rtc_paid": 1500})
        self.assertIn("1,500", b["message"])
        self.assertEqual(validate_badge(b), [])

    def test_zero(self):
        b = generate_total_bounties_badge({"total_rtc_paid": 0})
        self.assertIn("0", b["message"])


# ── Weekly growth badge ─────────────────────────────────────────────

class TestWeeklyGrowthBadge(unittest.TestCase):
    def test_positive(self):
        b = generate_weekly_growth_badge({"weekly_growth_pct": 15.5})
        self.assertIn("+15.5%", b["message"])

    def test_negative(self):
        b = generate_weekly_growth_badge({"weekly_growth_pct": -3.2})
        self.assertIn("-3.2%", b["message"])

    def test_zero(self):
        b = generate_weekly_growth_badge({"weekly_growth_pct": 0})
        self.assertEqual(b["message"], "0%")


# ── Top hunters badge ───────────────────────────────────────────────

class TestTopHuntersBadge(unittest.TestCase):
    def test_with_hunters(self):
        hunters = [
            {"name": "alice", "total_rtc": 500},
            {"name": "bob", "total_rtc": 300},
            {"name": "charlie", "total_rtc": 100},
        ]
        b = generate_top_hunters_badge(hunters)
        self.assertIn("alice", b["message"])
        self.assertIn("500", b["message"])
        self.assertEqual(validate_badge(b), [])

    def test_empty(self):
        b = generate_top_hunters_badge([])
        self.assertEqual(b["message"], "none yet")

    def test_limits_to_three(self):
        hunters = [{"name": f"h{i}", "total_rtc": i} for i in range(10)]
        b = generate_top_hunters_badge(hunters)
        self.assertEqual(b["message"].count("|"), 2)  # 3 entries = 2 separators


# ── Category badge ──────────────────────────────────────────────────

class TestCategoryBadge(unittest.TestCase):
    def test_docs(self):
        b = generate_category_badge("docs", 5)
        self.assertEqual(b["message"], "5")
        self.assertIn("Docs", b["label"])

    def test_bugs(self):
        b = generate_category_badge("bugs", 12)
        self.assertIn("Bug", b["label"])

    def test_unknown_category(self):
        b = generate_category_badge("misc", 3)
        self.assertEqual(validate_badge(b), [])


# ── Hunter badge ────────────────────────────────────────────────────

class TestHunterBadge(unittest.TestCase):
    def test_basic(self):
        h = {"name": "B1tor", "total_rtc": 705, "rank": 1, "merged_prs": 8}
        b = generate_hunter_badge(h)
        self.assertIn("B1tor", b["label"])
        self.assertIn("705", b["message"])
        self.assertIn("#1", b["message"])
        self.assertEqual(validate_badge(b), [])


# ── Full generation test ────────────────────────────────────────────

class TestGenerateAll(unittest.TestCase):
    def test_generates_files(self):
        data = {
            "network_status": "healthy",
            "total_rtc_paid": 1500,
            "weekly_growth_pct": 12.5,
            "hunters": [
                {"name": "alice", "total_rtc": 500, "rank": 1, "merged_prs": 5},
                {"name": "bob", "total_rtc": 300, "rank": 2, "merged_prs": 3},
            ],
            "categories": {"docs": 3, "bugs": 7, "outreach": 2},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            written = generate_all_badges(data, tmpdir)
            self.assertTrue(len(written) >= 8)  # 4 fixed + 3 cats + 2 hunters + manifest

            # Verify all JSON files are valid
            for path in written:
                with open(path) as f:
                    content = json.load(f)
                if "manifest" not in path:
                    self.assertEqual(validate_badge(content), [], f"Invalid: {path}")

    def test_manifest(self):
        data = {"network_status": "healthy", "hunters": [], "categories": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_all_badges(data, tmpdir)
            manifest_path = os.path.join(tmpdir, "manifest.json")
            self.assertTrue(os.path.exists(manifest_path))
            with open(manifest_path) as f:
                manifest = json.load(f)
            self.assertIn("generated_at", manifest)
            self.assertIn("badge_count", manifest)

    def test_deterministic(self):
        data = {
            "network_status": "healthy",
            "total_rtc_paid": 100,
            "weekly_growth_pct": 0,
            "hunters": [{"name": "x", "total_rtc": 10, "rank": 1, "merged_prs": 1}],
            "categories": {},
        }
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            generate_all_badges(data, d1)
            generate_all_badges(data, d2)
            for fname in os.listdir(d1):
                if fname == "manifest.json":
                    continue  # timestamps differ
                with open(os.path.join(d1, fname)) as f1, open(os.path.join(d2, fname)) as f2:
                    self.assertEqual(json.load(f1), json.load(f2), f"Non-deterministic: {fname}")


# ── Contributors parser test ────────────────────────────────────────

class TestParseContributors(unittest.TestCase):
    def test_table_format(self):
        text = """
| Hunter | RTC |
|--------|-----|
| @alice | 200 RTC |
| @bob   | 150 RTC |
"""
        hunters = _parse_contributors(text)
        self.assertEqual(len(hunters), 2)
        self.assertEqual(hunters[0]["name"], "alice")
        self.assertEqual(hunters[0]["total_rtc"], 200)
        self.assertEqual(hunters[0]["rank"], 1)

    def test_list_format(self):
        text = """
- @alice — 200 RTC
- @bob — 150 RTC
"""
        hunters = _parse_contributors(text)
        self.assertTrue(len(hunters) >= 2)

    def test_empty(self):
        self.assertEqual(_parse_contributors(""), [])


if __name__ == "__main__":
    unittest.main()
