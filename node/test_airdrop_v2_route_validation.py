import os
import tempfile
import unittest

from flask import Flask

from airdrop_v2 import AirdropV2, init_airdrop_routes


class TestAirdropV2RouteValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.airdrop = AirdropV2(db_path=self.tmp.name)
        app = Flask(__name__)
        init_airdrop_routes(app, self.airdrop, self.tmp.name)
        app.config["TESTING"] = False
        self.client = app.test_client()

    def tearDown(self):
        self.client = None
        os.unlink(self.tmp.name)

    def test_public_routes_reject_non_string_fields_without_500(self):
        cases = [
            (
                "eligibility_github_list",
                "/api/airdrop/eligibility",
                {"github_username": [], "wallet_address": "x" * 32, "chain": "solana"},
            ),
            (
                "eligibility_wallet_dict",
                "/api/airdrop/eligibility",
                {"github_username": "octocat", "wallet_address": {}, "chain": "solana"},
            ),
            (
                "eligibility_chain_list",
                "/api/airdrop/eligibility",
                {"github_username": "octocat", "wallet_address": "x" * 32, "chain": []},
            ),
            (
                "claim_tier_dict",
                "/api/airdrop/claim",
                {
                    "github_username": "octocat",
                    "wallet_address": "x" * 32,
                    "chain": "solana",
                    "tier": {},
                },
            ),
            (
                "bridge_from_list",
                "/api/bridge/lock",
                {
                    "from_address": [],
                    "to_address": "dest_wallet_12345",
                    "from_chain": "solana",
                    "to_chain": "base",
                    "amount_wrtc": 1,
                },
            ),
        ]

        for name, path, payload in cases:
            with self.subTest(name=name):
                response = self.client.post(path, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("Internal Server Error", response.get_data(as_text=True))

    def test_bridge_lock_rejects_invalid_amount_without_500(self):
        base_payload = {
            "from_address": "source_wallet_12345",
            "to_address": "dest_wallet_12345",
            "from_chain": "solana",
            "to_chain": "base",
        }
        for amount_wrtc in ("not-a-number", "nan", "inf", {}, []):
            with self.subTest(amount_wrtc=amount_wrtc):
                response = self.client.post(
                    "/api/bridge/lock",
                    json={**base_payload, "amount_wrtc": amount_wrtc},
                )
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("Internal Server Error", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
