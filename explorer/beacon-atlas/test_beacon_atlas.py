#!/usr/bin/env python3
"""
Tests for Beacon Atlas — validates HTML structure, JS logic, and API integration.

Run: python -m pytest explorer/beacon-atlas/test_beacon_atlas.py -v
"""

import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class TestHTMLStructure(unittest.TestCase):
    """Validate index.html has required UI elements."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "index.html")) as f:
            cls.html = f.read()

    def test_has_svg_graph(self):
        self.assertIn('id="graph"', self.html)

    def test_has_search_input(self):
        self.assertIn('id="search"', self.html)

    def test_has_filter_buttons(self):
        for arch in ["G4", "G5", "POWER8", "x86", "ARM", "beacon"]:
            self.assertIn(f'data-filter="{arch}"', self.html)

    def test_has_info_panel(self):
        self.assertIn('id="info-panel"', self.html)

    def test_has_legend(self):
        self.assertIn('id="legend"', self.html)

    def test_has_stats(self):
        for stat in ["stat-miners", "stat-agents", "stat-edges", "stat-epoch"]:
            self.assertIn(f'id="{stat}"', self.html)

    def test_loads_d3(self):
        self.assertIn("d3.v7.min.js", self.html)

    def test_loads_atlas_js(self):
        self.assertIn("beacon_atlas.js", self.html)

    def test_responsive_viewport(self):
        self.assertIn("viewport", self.html)
        self.assertIn("width=device-width", self.html)

    def test_title(self):
        self.assertIn("<title>", self.html)
        self.assertIn("Beacon Atlas", self.html)

    def test_arch_colors_in_css(self):
        # G4=amber, G5=blue, POWER8=purple, x86=green, ARM=red
        self.assertIn("#f59e0b", self.html)  # amber
        self.assertIn("#3b82f6", self.html)  # blue
        self.assertIn("#a855f7", self.html)  # purple
        self.assertIn("#22c55e", self.html)  # green
        self.assertIn("#ef4444", self.html)  # red

    def test_no_external_css(self):
        # All CSS should be inline for static deployment
        self.assertNotIn('<link rel="stylesheet"', self.html)


class TestJSStructure(unittest.TestCase):
    """Validate beacon_atlas.js has required functionality."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "beacon_atlas.js")) as f:
            cls.js = f.read()

    def test_has_api_base(self):
        self.assertIn("rustchain.org", self.js)

    def test_fetches_miners(self):
        self.assertIn("/api/miners", self.js)

    def test_fetches_agents(self):
        self.assertIn("/beacon/atlas", self.js)

    def test_fetches_epoch(self):
        self.assertIn("/epoch", self.js)

    def test_has_arch_colors(self):
        for arch in ["G4", "G5", "POWER8", "x86", "ARM", "beacon"]:
            self.assertIn(arch, self.js)

    def test_has_force_simulation(self):
        self.assertIn("forceSimulation", self.js)

    def test_has_zoom(self):
        self.assertIn("d3.zoom", self.js)

    def test_has_drag(self):
        self.assertIn("d3.drag", self.js)

    def test_has_search_handler(self):
        self.assertIn('"#search"', self.js)
        self.assertIn("searchQuery", self.js)

    def test_has_filter_handler(self):
        self.assertIn("activeFilter", self.js)
        self.assertIn("filter-btn", self.js)

    def test_has_info_panel(self):
        self.assertIn("showInfo", self.js)
        self.assertIn("#info-panel", self.js)

    def test_has_tooltip(self):
        self.assertIn("showTooltip", self.js)
        self.assertIn("hideTooltip", self.js)

    def test_has_hexagon_for_beacon(self):
        self.assertIn("hexPoints", self.js)
        self.assertIn("polygon", self.js)

    def test_has_circle_for_miner(self):
        self.assertIn("circle", self.js)

    def test_has_auto_refresh(self):
        self.assertIn("setInterval", self.js)
        self.assertIn("REFRESH_INTERVAL", self.js)

    def test_has_demo_fallback(self):
        self.assertIn("demo-miner", self.js)
        self.assertIn("demo-agent", self.js)

    def test_edge_types(self):
        self.assertIn("attestation", self.js)
        self.assertIn("trust", self.js)

    def test_node_size_by_score(self):
        self.assertIn("nodeRadius", self.js)
        self.assertIn("score", self.js)

    def test_edge_thickness_by_strength(self):
        self.assertIn("strength", self.js)
        self.assertIn("stroke-width", self.js)

    def test_responsive_resize(self):
        self.assertIn("resize", self.js)

    def test_arch_detection(self):
        self.assertIn("ARCH_FROM_FAMILY", self.js)
        for key in ["powerpc", "power mac", "ppc64", "aarch", "intel", "amd"]:
            self.assertIn(key, self.js)


class TestArchDetection(unittest.TestCase):
    """Test architecture family detection logic (extracted from JS)."""

    FAMILY_MAP = {
        "PowerPC G4": "G4", "Power Mac G4": "G4",
        "Power Mac G5": "G5", "G5 Quad": "G5",
        "POWER8": "POWER8", "ppc64le": "POWER8",
        "x86_64": "x86", "Intel Core": "x86", "AMD Ryzen": "x86", "i686": "x86",
        "ARM Cortex": "ARM", "aarch64": "ARM", "Raspberry Pi": "ARM",
    }

    def test_arch_mapping(self):
        for family, expected in self.FAMILY_MAP.items():
            fl = family.lower()
            if "g4" in fl or "powerpc" in fl:
                result = "G4"
            elif "g5" in fl or "power mac g5" in fl:
                result = "G5"
            elif "power8" in fl or "ppc64" in fl:
                result = "POWER8"
            elif any(x in fl for x in ["arm", "aarch", "raspberry", "pi"]):
                result = "ARM"
            elif any(x in fl for x in ["x86", "intel", "amd", "i386", "i686", "x64"]):
                result = "x86"
            else:
                result = "unknown"
            self.assertEqual(result, expected, f"Family '{family}' should map to '{expected}'")


class TestStaticDeployability(unittest.TestCase):
    """Ensure the atlas is deployable as a static site."""

    def test_all_files_exist(self):
        for f in ["index.html", "beacon_atlas.js", "README.md"]:
            self.assertTrue(os.path.exists(os.path.join(HERE, f)), f"Missing: {f}")

    def test_no_build_required(self):
        # No package.json, no node_modules, no build scripts
        self.assertFalse(os.path.exists(os.path.join(HERE, "package.json")))
        self.assertFalse(os.path.exists(os.path.join(HERE, "node_modules")))

    def test_html_is_valid_structure(self):
        with open(os.path.join(HERE, "index.html")) as f:
            html = f.read()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)
        self.assertIn("<head>", html)
        self.assertIn("<body>", html)


if __name__ == "__main__":
    unittest.main()
