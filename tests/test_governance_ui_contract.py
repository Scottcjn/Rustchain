from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GovernanceUiContractTest(unittest.TestCase):
    def test_governance_page_uses_backend_api_contract(self):
        html = (ROOT / "web" / "governance.html").read_text(encoding="utf-8")

        self.assertIn("api('/api/governance/propose'", html)
        self.assertIn("api('/api/governance/vote'", html)
        self.assertIn("api('/api/governance/proposals'", html)
        self.assertNotIn("api('/governance/", html)

        self.assertIn("miner_id:", html)
        self.assertIn("proposal_type:", html)
        self.assertIn("timestamp,", html)
        self.assertIn("signature:", html)

        self.assertIn('<option value="for">for</option>', html)
        self.assertIn('<option value="against">against</option>', html)
        self.assertIn('<option value="abstain">abstain</option>', html)
        self.assertNotIn('<option value="yes">yes</option>', html)
        self.assertNotIn('<option value="no">no</option>', html)

        self.assertIn("p.proposed_by", html)
        self.assertIn("p.votes_for", html)
        self.assertIn("p.votes_against", html)
        self.assertIn("p.votes_abstain", html)


if __name__ == "__main__":
    unittest.main()
