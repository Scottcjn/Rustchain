# SPDX-License-Identifier: MIT
"""Regression test for the SPARC substring-fallback over-reward bug (issue #8237).

``lookup_hardware()``'s partial-match fallback returned the FIRST key that
literally substring-matched the normalized probe id, with no regard for how
conservative that entry's multiplier was. ``normalize_id("SPARC-T")`` yields
``"sparc_t"``, which has no exact key in ``WORKSTATION_DATABASE`` but IS a
superstring of the generic ``"sparc"`` entry (Sun-4, 1987, 3.0x LEGENDARY) —
and of no other ``sparc_*`` key. So an unrecognised/newer SPARC generation
(e.g. a 2013 SPARC T5) graded at the SAME multiplier as 1987 silicon,
regardless of how modern it actually was.

FAILS on unmodified main: ``lookup_hardware("SPARC-T", "sparc").base_multiplier
== 3.0`` (the 1987 LEGENDARY row).
PASSES with the fix: the lookup anchors to the lowest ``base_multiplier``
across every entry sharing the matched family, which for SPARC is 2.5x
(ANCIENT, UltraSPARC III/IV) — never the family's priciest tier for hardware
whose generation wasn't identified.
"""

import os
import sys
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

from rustchain_hardware_database import (  # noqa: E402
    lookup_hardware,
    calculate_poa_multiplier,
    WORKSTATION_DATABASE,
)


class TestSparcSubstringFallbackConservative(unittest.TestCase):
    def test_unidentified_sparc_generation_does_not_grade_at_1987_rate(self):
        entry = lookup_hardware("SPARC-T", "sparc")
        self.assertIsNotNone(entry, "SPARC-T should still resolve to *some* SPARC entry")
        self.assertLess(
            entry.base_multiplier, 3.0,
            f"SPARC-T (unidentified generation) graded at {entry.base_multiplier}x — "
            "the 1987 LEGENDARY rate is only correct for genuinely 1987-era SPARC "
            "hardware, not an unrecognised/newer probe string.",
        )

    def test_conservative_match_equals_family_minimum(self):
        entry = lookup_hardware("SPARC-T", "sparc")
        family_min = min(
            e.base_multiplier for e in WORKSTATION_DATABASE.values() if e.family == "sparc"
        )
        self.assertEqual(
            entry.base_multiplier, family_min,
            "an unidentified SPARC generation must grade at the family's lowest "
            "known multiplier, not an arbitrary substring-matched one",
        )

    def test_calculate_poa_multiplier_end_to_end(self):
        mult, tier, _rarity, _name = calculate_poa_multiplier("sparc", "SPARC-T")
        self.assertLess(mult, 3.0)
        self.assertNotEqual(tier, "LEGENDARY")

    def test_exact_generation_match_is_unaffected(self):
        # A precisely-reported generation must still resolve to its own
        # entry, not get dragged down to the family minimum.
        entry = lookup_hardware("ultrasparc_ii", "sparc")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "UltraSPARC II")
        self.assertEqual(entry.base_multiplier, 3.0)


if __name__ == "__main__":
    unittest.main()
