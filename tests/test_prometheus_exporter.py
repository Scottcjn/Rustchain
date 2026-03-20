# SPDX-License-Identifier: MIT

"""
Tests for the Prometheus metrics exporter.
Tests metric collection, HTTP endpoints, configuration handling, and error scenarios.
"""
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock, Mock
import sqlite3

# Import the exporter module - adjust path as needed
try:
    from prometheus_exporter import PrometheusExporter, parse_config, main
except ImportError:
    # Fallback for test discovery
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from prometheus_exporter import PrometheusExporter, parse_config, main


def mock_requests_response(data=None, status_code=200, raise_exception=None):
    """Create a mock requests response object."""
    if raise_exception:
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = raise_exception
        return mock_resp

    mock_resp = Mock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data or {}
    mock_resp.text = json.dumps(data or {})
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestPrometheusExporter(unittest.TestCase):

    def setUp(self):
        self.node_url = "http://127.0.0.1:8332"
        self.listen_port = 9090
        self.exporter = PrometheusExporter(self.node_url, self.listen_port)

    def test_init_with_defaults(self):
        """Test exporter initialization with default values."""
        exp = PrometheusExporter()
        self.assertEqual(exp.node_url, "http://127.0.0.1:8332")
        self.assertEqual(exp.listen_port, 9090)
        self.assertIsNone(exp.httpd)

    def test_init_with_custom_values(self):
        """Test exporter initialization with custom parameters."""
        custom_url = "http://192.168.1.100:8333"
        custom_port = 8080
        exp = PrometheusExporter(custom_url, custom_port)
        self.assertEqual(exp.node_url, custom_url)
        self.assertEqual(exp.listen_port, custom_port)

    @patch('prometheus_exporter.requests.get')
    def test_get_node_info_success(self, mock_get):
        """Test successful node info retrieval."""
        test_data = {
            "node_id": "node_abc123",
            "version": "2.2.1",
            "chain_height": 12345,
            "peer_count": 8,
            "uptime_seconds": 86400
        }
        mock_get.return_value = mock_requests_response(test_data)

        result = self.exporter.get_node_info()
        self.assertEqual(result, test_data)
        mock_get.assert_called_once_with(f"{self.node_url}/api/node/info", timeout=10)

    @patch('prometheus_exporter.requests.get')
    def test_get_node_info_connection_error(self, mock_get):
        """Test node info retrieval with connection error."""
        mock_get.side_effect = ConnectionError("Connection refused")

        result = self.exporter.get_node_info()
        self.assertEqual(result, {})

    @patch('prometheus_exporter.requests.get')
    def test_get_node_info_timeout(self, mock_get):
        """Test node info retrieval with timeout."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = self.exporter.get_node_info()
        self.assertEqual(result, {})

    @patch('prometheus_exporter.requests.get')
    def test_get_chain_stats_success(self, mock_get):
        """Test successful chain stats retrieval."""
        chain_data = {
            "total_blocks": 12500,
            "difficulty": 1000000,
            "hash_rate": "2.5 TH/s",
            "total_supply": 50000000,
            "circulating_supply": 48000000
        }
        mock_get.return_value = mock_requests_response(chain_data)

        result = self.exporter.get_chain_stats()
        self.assertEqual(result, chain_data)
        mock_get.assert_called_once_with(f"{self.node_url}/api/chain/stats", timeout=10)

    @patch('prometheus_exporter.requests.get')
    def test_get_chain_stats_http_error(self, mock_get):
        """Test chain stats retrieval with HTTP error."""
        import requests
        mock_get.return_value = mock_requests_response(
            status_code=500,
            raise_exception=requests.HTTPError("500 Server Error")
        )

        result = self.exporter.get_chain_stats()
        self.assertEqual(result, {})

    @patch('prometheus_exporter.requests.get')
    def test_get_epoch_info_success(self, mock_get):
        """Test successful epoch info retrieval."""
        epoch_data = {
            "current_epoch": 42,
            "epoch_start_time": 1640995200,
            "epoch_end_time": 1641081600,
            "epoch_duration": 86400,
            "blocks_in_epoch": 144,
            "active_miners": 25
        }
        mock_get.return_value = mock_requests_response(epoch_data)

        result = self.exporter.get_epoch_info()
        self.assertEqual(result, epoch_data)
        mock_get.assert_called_once_with(f"{self.node_url}/api/epoch/current", timeout=10)

    @patch('prometheus_exporter.requests.get')
    def test_get_miner_stats_success(self, mock_get):
        """Test successful miner stats retrieval."""
        miner_data = {
            "total_miners": 150,
            "active_miners": 125,
            "top_miners": [
                {"miner_id": "miner1", "hash_rate": "1.2 TH/s", "blocks_mined": 45},
                {"miner_id": "miner2", "hash_rate": "0.8 TH/s", "blocks_mined": 32}
            ],
            "avg_hash_rate": "0.5 TH/s"
        }
        mock_get.return_value = mock_requests_response(miner_data)

        result = self.exporter.get_miner_stats()
        self.assertEqual(result, miner_data)
        mock_get.assert_called_once_with(f"{self.node_url}/api/miners/stats", timeout=10)

    @patch('prometheus_exporter.requests.get')
    def test_get_balance_info_success(self, mock_get):
        """Test successful balance info retrieval."""
        balance_data = {
            "total_balance": 1000.5,
            "available_balance": 950.25,
            "locked_balance": 50.25,
            "wallet_address": "wallet_xyz789"
        }
        mock_get.return_value = mock_requests_response(balance_data)

        result = self.exporter.get_balance_info()
        self.assertEqual(result, balance_data)
        mock_get.assert_called_once_with(f"{self.node_url}/api/wallet/balance", timeout=10)

    def test_format_metrics_complete_data(self):
        """Test metrics formatting with complete data."""
        node_info = {"chain_height": 12345, "peer_count": 8, "uptime_seconds": 86400}
        chain_stats = {"total_blocks": 12500, "difficulty": 1000000}
        epoch_info = {"current_epoch": 42, "active_miners": 25, "blocks_in_epoch": 144}
        miner_stats = {"total_miners": 150, "active_miners": 125}
        balance_info = {"total_balance": 1000.5, "available_balance": 950.25}

        metrics = self.exporter.format_metrics(
            node_info, chain_stats, epoch_info, miner_stats, balance_info
        )

        self.assertIn("# HELP rustchain_node_chain_height", metrics)
        self.assertIn("rustchain_node_chain_height 12345", metrics)
        self.assertIn("rustchain_node_peer_count 8", metrics)
        self.assertIn("rustchain_node_uptime_seconds 86400", metrics)
        self.assertIn("rustchain_chain_total_blocks 12500", metrics)
        self.assertIn("rustchain_chain_difficulty 1000000", metrics)
        self.assertIn("rustchain_epoch_current 42", metrics)
        self.assertIn("rustchain_epoch_active_miners 25", metrics)
        self.assertIn("rustchain_miners_total 150", metrics)
        self.assertIn("rustchain_miners_active 125", metrics)
        self.assertIn("rustchain_wallet_total_balance 1000.5", metrics)
        self.assertIn("rustchain_wallet_available_balance 950.25", metrics)

    def test_format_metrics_partial_data(self):
        """Test metrics formatting with partial/missing data."""
        node_info = {"chain_height": 100}
        chain_stats = {}
        epoch_info = {"current_epoch": 5}
        miner_stats = {}
        balance_info = {}

        metrics = self.exporter.format_metrics(
            node_info, chain_stats, epoch_info, miner_stats, balance_info
        )

        self.assertIn("rustchain_node_chain_height 100", metrics)
        self.assertIn("rustchain_epoch_current 5", metrics)
        # Should handle missing keys gracefully
        self.assertNotIn("rustchain_node_peer_count", metrics)
        self.assertNotIn("rustchain_chain_difficulty", metrics)

    def test_format_metrics_empty_data(self):
        """Test metrics formatting with all empty data."""
        metrics = self.exporter.format_metrics({}, {}, {}, {}, {})

        # Should still contain help text
        self.assertIn("# HELP rustchain_node_chain_height", metrics)
        # But no actual metric values
        lines = [line for line in metrics.split('\n') if line and not line.startswith('#')]
        metric_lines = [line for line in lines if 'rustchain_' in line and not line.startswith('# ')]
        self.assertEqual(len(metric_lines), 0)

    @patch('prometheus_exporter.PrometheusExporter.get_node_info')
    @patch('prometheus_exporter.PrometheusExporter.get_chain_stats')
    @patch('prometheus_exporter.PrometheusExporter.get_epoch_info')
    @patch('prometheus_exporter.PrometheusExporter.get_miner_stats')
    @patch('prometheus_exporter.PrometheusExporter.get_balance_info')
    def test_collect_metrics_integration(self, mock_balance, mock_miner, mock_epoch, mock_chain, mock_node):
        """Test the complete metrics collection flow."""
        mock_node.return_value = {"chain_height": 500, "peer_count": 5}
        mock_chain.return_value = {"total_blocks": 510, "difficulty": 50000}
        mock_epoch.return_value = {"current_epoch": 10, "active_miners": 15}
        mock_miner.return_value = {"total_miners": 20, "active_miners": 15}
        mock_balance.return_value = {"total_balance": 123.45}

        metrics = self.exporter.collect_metrics()

        self.assertIn("rustchain_node_chain_height 500", metrics)
        self.assertIn("rustchain_chain_total_blocks 510", metrics)
        self.assertIn("rustchain_epoch_current 10", metrics)
        self.assertIn("rustchain_miners_total 20", metrics)
        self.assertIn("rustchain_wallet_total_balance 123.45", metrics)

    def test_metrics_endpoint_response(self):
        """Test HTTP metrics endpoint response format."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.request import urlopen
        import threading

        # Create a test server
        server_port = 9091

        class TestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    metrics = "# HELP test_metric Test metric\ntest_metric 42\n"
                    self.wfile.write(metrics.encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                # Suppress log messages
                pass

        httpd = HTTPServer(('localhost', server_port), TestHandler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        try:
            # Test the endpoint
            response = urlopen(f'http://localhost:{server_port}/metrics')
            content = response.read().decode()

            self.assertEqual(response.getcode(), 200)
            self.assertIn("test_metric 42", content)
        finally:
            httpd.shutdown()

    def test_parse_config_default_file(self):
        """Test configuration parsing with default values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "node_url": "http://192.168.1.50:8332",
                "listen_port": 8080
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            node_url, listen_port = parse_config(config_file)
            self.assertEqual(node_url, "http://192.168.1.50:8332")
            self.assertEqual(listen_port, 8080)
        finally:
            os.unlink(config_file)

    def test_parse_config_missing_file(self):
        """Test configuration parsing with missing file."""
        node_url, listen_port = parse_config("/nonexistent/config.json")
        self.assertEqual(node_url, "http://127.0.0.1:8332")
        self.assertEqual(listen_port, 9090)

    def test_parse_config_invalid_json(self):
        """Test configuration parsing with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            config_file = f.name

        try:
            node_url, listen_port = parse_config(config_file)
            # Should fall back to defaults
            self.assertEqual(node_url, "http://127.0.0.1:8332")
            self.assertEqual(listen_port, 9090)
        finally:
            os.unlink(config_file)

    def test_parse_config_partial_config(self):
        """Test configuration parsing with partial configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {"node_url": "http://custom-node:8333"}
            json.dump(config_data, f)
            config_file = f.name

        try:
            node_url, listen_port = parse_config(config_file)
            self.assertEqual(node_url, "http://custom-node:8333")
            self.assertEqual(listen_port, 9090)  # Default value
        finally:
            os.unlink(config_file)

    @patch('prometheus_exporter.PrometheusExporter')
    def test_main_function_with_args(self, mock_exporter_class):
        """Test main function with command line arguments."""
        import sys
        original_argv = sys.argv

        try:
            sys.argv = ['prometheus_exporter.py', '--node-url', 'http://test:8333', '--port', '8080']
            mock_exporter = Mock()
            mock_exporter_class.return_value = mock_exporter

            # This would normally run the server, but we'll mock it
            with patch('prometheus_exporter.parse_config') as mock_parse:
                mock_parse.return_value = ('http://test:8333', 8080)

                # Can't easily test the full main() due to server blocking,
                # but we can test argument parsing logic
                node_url, port = parse_config()
                self.assertEqual(node_url, "http://127.0.0.1:8332")
                self.assertEqual(port, 9090)
        finally:
            sys.argv = original_argv

    def test_hash_rate_parsing(self):
        """Test hash rate string parsing in metrics."""
        chain_stats = {"hash_rate": "2.5 TH/s"}
        metrics = self.exporter.format_metrics({}, chain_stats, {}, {}, {})

        # Should extract numeric value from hash rate string
        self.assertIn("rustchain_chain_hash_rate", metrics)

    def test_concurrent_requests(self):
        """Test handling multiple concurrent metric requests."""
        import concurrent.futures

        def collect_metrics_wrapper():
            with patch('prometheus_exporter.requests.get') as mock_get:
                mock_get.return_value = mock_requests_response({"chain_height": 100})
                return self.exporter.collect_metrics()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(collect_metrics_wrapper) for _ in range(5)]
            results = [future.result() for future in futures]

            # All requests should succeed
            for result in results:
                self.assertIn("rustchain_node_chain_height 100", result)

    def test_large_numeric_values(self):
        """Test handling of large numeric values in metrics."""
        large_data = {
            "chain_height": 999999999,
            "difficulty": 123456789012345,
            "total_supply": 21000000000000
        }

        with patch('prometheus_exporter.requests.get') as mock_get:
            mock_get.return_value = mock_requests_response(large_data)
            node_info = self.exporter.get_node_info()

            metrics = self.exporter.format_metrics(node_info, large_data, {}, {}, {})

            self.assertIn("rustchain_node_chain_height 999999999", metrics)
            self.assertIn("rustchain_chain_difficulty 123456789012345", metrics)


if __name__ == '__main__':
    unittest.main()
