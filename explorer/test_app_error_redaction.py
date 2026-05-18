import unittest
from unittest.mock import patch

import requests

import app as explorer_app


class ExplorerAppErrorRedactionTests(unittest.TestCase):
    def setUp(self):
        explorer_app.app.config["TESTING"] = True
        self.client = explorer_app.app.test_client()

    @patch("app.requests.get")
    def test_miners_connection_error_does_not_leak_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "connect failed to internal-host.local:8000"
        )

        response = self.client.get("/api/miners")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "Connection error", "miners": []})
        self.assertNotIn("internal-host", response.get_data(as_text=True))

    @patch("app.requests.get")
    def test_miner_detail_connection_error_does_not_leak_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("secret timeout detail")

        response = self.client.get("/api/miner/alice")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "Connection error"})
        self.assertNotIn("secret timeout detail", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
