# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_JS = ROOT / "site" / "beacon" / "ui.js"
STYLES = ROOT / "site" / "beacon" / "styles.css"


class TestBeaconContractHistoryUI(unittest.TestCase):
    def test_selected_agent_panel_renders_complete_timeline_fields(self):
        source = UI_JS.read_text(encoding="utf-8")

        self.assertIn(
            "import { buildContractHistory, formatContractTimestamp } "
            "from './contract-history.mjs';",
            source,
        )
        self.assertIn("buildContractHistory(CONTRACTS, agentId)", source)
        self.assertIn("-- CONTRACT HISTORY (${agentContracts.length}) --", source)
        self.assertIn('class="contract-timeline" role="list"', source)
        self.assertIn("formatContractTimestamp(c.created_at)", source)
        self.assertIn("direction-${escapeHtml(c.direction)}", source)
        self.assertIn("state-${escapeHtml(c.state)}", source)
        self.assertIn("${escapeHtml(c.amount)} ${escapeHtml(c.currency)}", source)
        self.assertIn("TERM ${escapeHtml(c.term || '?')}", source)
        self.assertIn("ID ${escapeHtml(c.id)}", source)
        self.assertIn("No contracts recorded for this agent.", source)

    def test_timeline_styles_cover_layout_and_terminal_states(self):
        source = STYLES.read_text(encoding="utf-8")

        for selector in (
            ".contract-timeline",
            ".contract-timeline-item",
            ".contract-timeline-marker",
            ".contract-timeline-time",
            ".contract-timeline-details",
            ".direction-outgoing",
            ".direction-incoming",
            ".state-completed",
            ".state-rejected",
        ):
            self.assertIn(selector, source)


if __name__ == "__main__":
    unittest.main()
