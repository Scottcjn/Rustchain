# SPDX-License-Identifier: MIT

"""
Tests for the Prometheus metrics exporter.
Tests metric collection, API scraping, error handling, and full export workflow.
"""
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import time
from prometheus_client import CollectorRegistry

# Import the exporter module (assuming it will be created)
try:
    from prometheus_exporter import (
        RustChainCollector,
        PrometheusConfig,
        create_app,
        parse_config,
        validate_node_connection
    )
except ImportError:
    # Mock for development - tests will fail until exporter is implemented
    class RustChainCollector:
        pass
    class PrometheusConfig:
        pass
    def create_app():
        pass
    def parse_config():
        pass
    def validate_node_connection():
        pass


def mock_api_response(data, status_code=200):
    """Create a mock HTTP response object"""
    response = MagicMock()
    response.status_code = status_code
    response.ok = (status_code == 200)
    response.json.return_value = data
    response.text = json.dumps(data)
    return response


class TestPrometheusConfig(unittest.TestCase):

    def test_config_defaults(self):
        """Test default configuration values"""
        config = PrometheusConfig()
        self.assertEqual(config.node_url, "http://localhost:3030")
        self.assertEqual(config.listen_port, 9100)
        self.assertEqual(config.scrape_interval, 30)

    def test_config_from_dict(self):
        """Test configuration from dictionary"""
        cfg_data = {
            "node_url": "http://192.168.1.100:3030",
            "listen_port": 8080,
            "scrape_interval": 60
        }
        config = PrometheusConfig(cfg_data)
        self.assertEqual(config.node_url, "http://192.168.1.100:3030")
        self.assertEqual(config.listen_port, 8080)
        self.assertEqual(config.scrape_interval, 60)


class TestConfigParsing(unittest.TestCase):

    def test_parse_yaml_config(self):
        """Test parsing YAML configuration file"""
        yaml_content = """
node_url: "http://testnode:3030"
listen_port: 9200
scrape_interval: 45
log_level: "INFO"
"""
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            with patch("os.path.exists", return_value=True):
                config = parse_config("test_config.yml")
                self.assertEqual(config.node_url, "http://testnode:3030")
                self.assertEqual(config.listen_port, 9200)
                self.assertEqual(config.scrape_interval, 45)

    def test_parse_missing_config_file(self):
        """Test handling of missing configuration file"""
        with patch("os.path.exists", return_value=False):
            config = parse_config("missing_config.yml")
            # Should return default config
            self.assertEqual(config.node_url, "http://localhost:3030")

    def test_parse_invalid_yaml(self):
        """Test handling of invalid YAML content"""
        invalid_yaml = "node_url: [invalid: yaml: content"
        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with patch("os.path.exists", return_value=True):
                config = parse_config("invalid.yml")
                # Should fall back to defaults on parse error
                self.assertEqual(config.node_url, "http://localhost:3030")


class TestNodeConnection(unittest.TestCase):

    @patch("requests.get")
    def test_validate_connection_success(self, mock_get):
        """Test successful node connection validation"""
        mock_get.return_value = mock_api_response({"status": "healthy"})
        result = validate_node_connection("http://localhost:3030")
        self.assertTrue(result)

    @patch("requests.get")
    def test_validate_connection_failure(self, mock_get):
        """Test failed node connection validation"""
        mock_get.side_effect = Exception("Connection refused")
        result = validate_node_connection("http://localhost:3030")
        self.assertFalse(result)

    @patch("requests.get")
    def test_validate_connection_http_error(self, mock_get):
        """Test HTTP error during connection validation"""
        mock_get.return_value = mock_api_response({}, status_code=500)
        result = validate_node_connection("http://localhost:3030")
        self.assertFalse(result)


class TestRustChainCollector(unittest.TestCase):

    def setUp(self):
        self.config = PrometheusConfig({
            "node_url": "http://localhost:3030",
            "scrape_interval": 30
        })
        self.collector = RustChainCollector(self.config)

    @patch("requests.get")
    def test_collect_node_status_metrics(self, mock_get):
        """Test collection of basic node status metrics"""
        api_responses = [
            mock_api_response({
                "node_id": "test-node-123",
                "uptime_seconds": 3600,
                "peers_connected": 5,
                "chain_height": 12450
            }),
            mock_api_response({
                "current_epoch": 1245,
                "epoch_progress": 0.67,
                "next_epoch_in": 1800
            })
        ]
        mock_get.side_effect = api_responses

        metrics = list(self.collector.collect())
        self.assertGreater(len(metrics), 0)

        # Verify specific metrics are present
        metric_names = [m.name for m in metrics]
        self.assertIn("rustchain_node_uptime_seconds", metric_names)
        self.assertIn("rustchain_peers_connected", metric_names)
        self.assertIn("rustchain_chain_height", metric_names)

    @patch("requests.get")
    def test_collect_miner_metrics(self, mock_get):
        """Test collection of miner activity metrics"""
        mock_get.return_value = mock_api_response({
            "active_miners": 12,
            "mining_difficulty": 4.56,
            "hashrate_estimate": 1250000,
            "blocks_mined_hour": 8
        })

        metrics = list(self.collector.collect())
        metric_names = [m.name for m in metrics]

        self.assertIn("rustchain_active_miners", metric_names)
        self.assertIn("rustchain_mining_difficulty", metric_names)
        self.assertIn("rustchain_hashrate_estimate", metric_names)

    @patch("requests.get")
    def test_collect_epoch_metrics(self, mock_get):
        """Test collection of epoch-related metrics"""
        mock_get.return_value = mock_api_response({
            "current_epoch": 1245,
            "epoch_progress": 0.75,
            "blocks_this_epoch": 18,
            "target_blocks_per_epoch": 24,
            "epoch_start_time": int(time.time()) - 3600
        })

        metrics = list(self.collector.collect())
        metric_names = [m.name for m in metrics]

        self.assertIn("rustchain_current_epoch", metric_names)
        self.assertIn("rustchain_epoch_progress", metric_names)
        self.assertIn("rustchain_blocks_this_epoch", metric_names)

    @patch("requests.get")
    def test_collect_wallet_metrics(self, mock_get):
        """Test collection of wallet and transaction metrics"""
        mock_get.return_value = mock_api_response({
            "total_wallets": 1450,
            "active_wallets_24h": 89,
            "pending_transactions": 23,
            "transactions_per_second": 2.4
        })

        metrics = list(self.collector.collect())
        metric_names = [m.name for m in metrics]

        self.assertIn("rustchain_total_wallets", metric_names)
        self.assertIn("rustchain_active_wallets_24h", metric_names)
        self.assertIn("rustchain_pending_transactions", metric_names)

    @patch("requests.get")
    def test_collect_api_error_handling(self, mock_get):
        """Test handling of API errors during metric collection"""
        mock_get.side_effect = Exception("API unreachable")

        # Should not raise exception, but return error metric
        metrics = list(self.collector.collect())
        metric_names = [m.name for m in metrics]

        self.assertIn("rustchain_scrape_errors_total", metric_names)

    @patch("requests.get")
    def test_collect_timeout_handling(self, mock_get):
        """Test handling of API timeouts"""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        metrics = list(self.collector.collect())
        metric_names = [m.name for m in metrics]

        # Should include error metric for timeout
        self.assertIn("rustchain_scrape_errors_total", metric_names)

    @patch("requests.get")
    def test_collect_partial_data_handling(self, mock_get):
        """Test handling of partial/incomplete API responses"""
        # API returns some data but missing expected fields
        mock_get.return_value = mock_api_response({
            "node_id": "partial-node",
            "uptime_seconds": 7200
            # Missing peers_connected, chain_height, etc.
        })

        metrics = list(self.collector.collect())
        self.assertGreater(len(metrics), 0)

        # Should still collect available metrics
        metric_names = [m.name for m in metrics]
        self.assertIn("rustchain_node_uptime_seconds", metric_names)


class TestFlaskApp(unittest.TestCase):

    def setUp(self):
        self.config = PrometheusConfig()
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def test_metrics_endpoint(self):
        """Test /metrics endpoint returns Prometheus format"""
        with patch("prometheus_client.generate_latest") as mock_generate:
            mock_generate.return_value = b"# HELP rustchain_node_uptime_seconds Node uptime"

            response = self.client.get("/metrics")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, "text/plain; charset=utf-8")

    def test_health_endpoint(self):
        """Test /health endpoint"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")

    def test_info_endpoint(self):
        """Test /info endpoint returns exporter information"""
        response = self.client.get("/info")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn("exporter", data)
        self.assertIn("version", data)
        self.assertIn("node_url", data)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete export workflow"""

    @patch("requests.get")
    def test_full_export_workflow(self, mock_get):
        """Test complete metric collection and export workflow"""
        # Setup mock API responses for different endpoints
        api_responses = {
            "/api/status": {
                "node_id": "integration-test-node",
                "uptime_seconds": 7200,
                "peers_connected": 8,
                "chain_height": 15600
            },
            "/api/epoch": {
                "current_epoch": 1560,
                "epoch_progress": 0.45,
                "blocks_this_epoch": 11
            },
            "/api/miners": {
                "active_miners": 15,
                "mining_difficulty": 3.8,
                "hashrate_estimate": 2100000
            }
        }

        def mock_api_call(url, **kwargs):
            for endpoint, data in api_responses.items():
                if endpoint in url:
                    return mock_api_response(data)
            return mock_api_response({}, status_code=404)

        mock_get.side_effect = mock_api_call

        # Create collector and registry
        config = PrometheusConfig()
        registry = CollectorRegistry()
        collector = RustChainCollector(config)
        registry.register(collector)

        # Collect metrics
        metrics = list(collector.collect())

        # Verify comprehensive metric collection
        self.assertGreater(len(metrics), 5)

        metric_names = [m.name for m in metrics]
        expected_metrics = [
            "rustchain_node_uptime_seconds",
            "rustchain_peers_connected",
            "rustchain_chain_height",
            "rustchain_current_epoch",
            "rustchain_active_miners"
        ]

        for expected in expected_metrics:
            self.assertIn(expected, metric_names, f"Missing metric: {expected}")

    def test_configuration_file_integration(self):
        """Test loading configuration from file and creating exporter"""
        config_content = {
            "node_url": "http://test-integration:3030",
            "listen_port": 9150,
            "scrape_interval": 20
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            import yaml
            yaml.dump(config_content, f)
            config_file = f.name

        try:
            config = parse_config(config_file)
            self.assertEqual(config.node_url, "http://test-integration:3030")
            self.assertEqual(config.listen_port, 9150)

            # Verify we can create collector with this config
            collector = RustChainCollector(config)
            self.assertIsNotNone(collector)

        finally:
            os.unlink(config_file)

    @patch("requests.get")
    def test_error_recovery_workflow(self, mock_get):
        """Test that exporter continues working after API errors"""
        # First call fails, second succeeds
        mock_get.side_effect = [
            Exception("Temporary network error"),
            mock_api_response({
                "node_id": "recovery-test",
                "uptime_seconds": 1800,
                "peers_connected": 3
            })
        ]

        collector = RustChainCollector(PrometheusConfig())

        # First collection should handle error gracefully
        metrics1 = list(collector.collect())
        error_metrics = [m for m in metrics1 if "error" in m.name]
        self.assertGreater(len(error_metrics), 0)

        # Second collection should work normally
        metrics2 = list(collector.collect())
        success_metrics = [m for m in metrics2 if "uptime" in m.name]
        self.assertGreater(len(success_metrics), 0)


if __name__ == "__main__":
    unittest.main()
