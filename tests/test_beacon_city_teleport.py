# SPDX-License-Identifier: MIT

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BEACON = ROOT / "site" / "beacon"


class BeaconCityTeleportIntegrationTests(unittest.TestCase):
    def test_hud_exposes_accessible_city_teleport_select(self):
        html = (BEACON / "index.html").read_text(encoding="utf-8")

        self.assertIn('class="city-teleport"', html)
        self.assertIn('for="hud-city-teleport"', html)
        self.assertIn('id="hud-city-teleport"', html)
        self.assertIn('aria-label="Teleport camera to a city"', html)

    def test_ui_builds_safe_options_and_reuses_city_selection(self):
        ui = (BEACON / "ui.js").read_text(encoding="utf-8")

        self.assertIn("initCityTeleport();", ui)
        self.assertIn("buildCityTeleportGroups(CITIES, REGIONS)", ui)
        self.assertIn("document.createElement('optgroup')", ui)
        self.assertIn("document.createElement('option')", ui)
        self.assertIn("option.textContent = city.name", ui)
        self.assertIn("resolveTeleportCity(CITIES, select.value)", ui)
        self.assertIn("if (city) selectCity(city.id);", ui)

    def test_select_is_interactive_above_the_canvas_and_responsive(self):
        css = (BEACON / "styles.css").read_text(encoding="utf-8")

        self.assertIn(".city-teleport {", css)
        self.assertIn("pointer-events: auto", css)
        self.assertIn(".city-teleport-select {", css)
        self.assertIn("max-width: calc(100vw - 70px)", css)
        self.assertIn(".city-teleport-select:focus-visible", css)


if __name__ == "__main__":
    unittest.main()
