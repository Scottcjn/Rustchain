import os
import tempfile
import unittest

from tools.rent_a_relic import server


class RentARelicValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.app.config["TESTING"] = True
        server.app.config["DB_PATH"] = os.path.join(self.tmp.name, "rent.db")
        os.environ["RC_ADMIN_KEY"] = "admin"
        self.client = server.app.test_client()

    def tearDown(self):
        os.environ.pop("RC_ADMIN_KEY", None)
        server.app.config.pop("DB_PATH", None)
        self.tmp.cleanup()

    def test_reserve_rejects_non_string_agent_id(self):
        resp = self.client.post(
            "/relic/reserve",
            json={
                "agent_id": {"id": "agent"},
                "machine_id": "g5-dual",
                "duration_hours": 4,
                "rtc_amount": 32.0,
            },
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("agent_id must be a string", resp.get_data(as_text=True))

    def test_complete_rejects_non_string_output_hash(self):
        resp = self.client.post(
            "/relic/complete/session-1",
            json={"output_hash": {"sha256": "abc"}},
            headers={"X-Admin-Key": "admin"},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("output_hash must be a string", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
