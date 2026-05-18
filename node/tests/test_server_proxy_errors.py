import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

import server_proxy


class ServerProxyErrorTests(unittest.TestCase):
    def setUp(self):
        server_proxy.app.config["TESTING"] = True
        self.client = server_proxy.app.test_client()

    @patch("server_proxy.requests.get")
    def test_proxy_exception_does_not_leak_message(self, mock_get):
        mock_get.side_effect = RuntimeError("secret filesystem path")

        response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 500)
        body = response.get_json()
        self.assertEqual(body, {"error": "Proxy error"})
        self.assertNotIn("secret filesystem path", response.get_data(as_text=True))

    @patch("server_proxy.requests.get")
    def test_upstream_500_body_is_redacted(self, mock_get):
        upstream = Mock()
        upstream.status_code = 500
        upstream.headers = {"Content-Type": "text/plain"}
        upstream.text = "Traceback: database password is hunter2"
        mock_get.return_value = upstream

        response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "Upstream server error"})
        self.assertNotIn("hunter2", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
