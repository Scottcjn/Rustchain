#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A real Power Mac does not call itself "powerpc".

`platform.machine()` on Mac OS X PowerPC returns **"Power Macintosh"**, which
contains neither `"ppc"` nor `"powerpc"`. Every check written as

    if "powerpc" in arch or "ppc" in arch:

therefore fails to recognise a genuine Power Mac G4 or G5 by its own
architecture string.

The node already knew this. `POWERPC_ARCHES` lists `"power macintosh"`, and so
do the two vintage-relaxation sets. Only the cache-profile check used the bare
substrings, which is the one place that decided whether the G5 was accepted, so
its arch fast-path never fired and validation fell through to a ratio the
hardware cannot produce.

The clients had the same bug twice over: `has_altivec` and the PowerPC ROM path
were both gated on `"ppc" in arch`, so a real Power Mac reported no AltiVec and
skipped the PowerPC ROM check entirely.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)
os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)

_spec = importlib.util.spec_from_file_location(
    "rc_node_ppc", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_ppc"] = MOD
_spec.loader.exec_module(MOD)


class ArchLabelTest(unittest.TestCase):

    def test_the_label_a_real_power_mac_reports(self):
        """platform.machine() on OS X PowerPC. This is the whole bug."""
        self.assertTrue(MOD._is_powerpc_arch_label("Power Macintosh"))
        self.assertTrue(MOD._is_powerpc_arch_label("power macintosh"))

    def test_the_obvious_spellings_still_work(self):
        for label in ("ppc", "ppc64", "ppc64le", "powerpc", "PowerPC",
                      "powerpc64", "g4", "g5", "power8"):
            self.assertTrue(MOD._is_powerpc_arch_label(label), label)

    def test_non_powerpc_labels_are_rejected(self):
        for label in ("x86_64", "amd64", "aarch64", "arm64", "riscv64",
                      "i386", "mips", "sparc64", "", None):
            self.assertFalse(MOD._is_powerpc_arch_label(label), repr(label))

    def test_junk_does_not_raise(self):
        for junk in (12345, [], {}, b"ppc"):
            self.assertIsInstance(MOD._is_powerpc_arch_label(junk), bool)


class CacheProfileAcceptsTheArchTagTest(unittest.TestCase):
    """With the tag recognised, the strong path works instead of the bypass."""

    def _fp(self, cache_data=None, simd_data=None):
        checks = {}
        if cache_data is not None:
            checks["cache_timing"] = {"passed": True, "data": cache_data}
        if simd_data is not None:
            checks["simd_identity"] = {"passed": True, "data": simd_data}
        return {"checks": checks}

    def test_power_macintosh_in_cache_timing_is_accepted(self):
        self.assertTrue(MOD._has_powerpc_cache_profile(
            self._fp(cache_data={"arch": "Power Macintosh",
                                 "l2_l1_ratio": 0.801})))

    def test_power_macintosh_in_simd_identity_is_accepted(self):
        """The client already emitted arch here; nothing was reading it."""
        self.assertTrue(MOD._has_powerpc_cache_profile(
            self._fp(cache_data={"l2_l1_ratio": 0.801},
                     simd_data={"arch": "power macintosh"})))

    def test_an_x86_arch_tag_does_not_pass_the_cache_profile(self):
        self.assertFalse(MOD._has_powerpc_cache_profile(
            self._fp(cache_data={"arch": "x86_64", "l2_l1_ratio": 0.801})))

    def test_the_degenerate_ratio_bypass_is_still_there_as_a_backstop(self):
        """Deployed clients that send no arch tag must keep working."""
        self.assertTrue(MOD._cache_measurement_is_degenerate(
            {"l2_l1_ratio": 0.801}))


class ClientsAgreeTest(unittest.TestCase):
    """All three client copies must recognise the same label."""

    def test_every_client_recognises_power_macintosh(self):
        for platform_dir in ("macos", "linux", "windows"):
            path = os.path.join(ROOT, "miners", platform_dir,
                                "fingerprint_checks.py")
            src = open(path).read()
            self.assertIn("power macintosh", src,
                          f"{platform_dir} client cannot see a real Power Mac")
            self.assertNotIn('or "ppc" in arch', src,
                             f"{platform_dir} still uses the substring test")

    def test_every_client_tags_cache_timing_with_arch(self):
        for platform_dir in ("macos", "linux", "windows"):
            path = os.path.join(ROOT, "miners", platform_dir,
                                "fingerprint_checks.py")
            src = open(path).read()
            self.assertIn('"arch": platform.machine().lower()', src,
                          f"{platform_dir} does not tag cache_timing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
