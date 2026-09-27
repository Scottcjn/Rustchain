# SPDX-License-Identifier: MIT

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BEACON = ROOT / "site" / "beacon"


class BeaconAgentLeaderboardIntegrationTests(unittest.TestCase):
    def test_atlas_exposes_an_accessible_leaderboard_sidebar(self):
        html = (BEACON / "index.html").read_text(encoding="utf-8")

        self.assertIn('class="agent-leaderboard"', html)
        self.assertIn('aria-label="Top Beacon agents"', html)

    def test_ui_renders_safe_selectable_rows_and_both_modes(self):
        source = (BEACON / "ui.js").read_text(encoding="utf-8")

        self.assertIn(
            "import { buildAgentLeaderboard } from './leaderboard.mjs';",
            source,
        )
        self.assertIn("buildAgentLeaderboard(", source)
        self.assertIn("modeButton.setAttribute('aria-pressed'", source)
        self.assertIn("rowName.textContent = entry.name", source)
        self.assertIn("row.addEventListener('click', () => selectAgent(entry.id))", source)
        self.assertIn("leaderboardRoot.replaceChildren", source)

    def test_sidebar_is_interactive_scrollable_and_responsive(self):
        css = (BEACON / "styles.css").read_text(encoding="utf-8")

        for fragment in (
            ".agent-leaderboard {",
            "pointer-events: auto",
            ".leaderboard-list {",
            "overflow-y: auto",
            ".leaderboard-row:focus-visible",
            "@media (max-width: 768px)",
        ):
            self.assertIn(fragment, css)


if __name__ == "__main__":
    unittest.main()
