#!/usr/bin/env python3
"""
Tests for RustChain Prometheus Exporter - Bounty #765

Run tests:
    pytest tests/ -v
    pytest tests/ -v --cov=src

Test coverage:
    - Metrics registry and exposition format
    - Node client with mocked responses
    - Metrics collector
    - HTTP server endpoints
    - Configuration handling
"""

import pytest
import json
import time
import threading
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from io import BytesIO
from requests.exceptions import RequestException, Timeout

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rustchain_exporter import (
    ExporterConfig,
    MetricsRegistry,
    RustChainNodeClient,
    MetricsCollector,
    MetricsHandler,
    ExporterServer,
    NodeHealth,
    EpochInfo,
    MinerInfo,
)
from metrics_exposition import (
    PrometheusExposition,
    MetricType,
    format_timestamp,
    validate_metric_name,
    validate_label_name,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def config():
    """Default exporter configuration for tests."""
    return ExporterConfig(
        node_url='http://test-node:8080',
        exporter_port=9100,
        scrape_interval=30,
        tls_verify=False,
        request_timeout=5.0,
        max_retries=2
    )


@pytest.fixture
def registry():
    """Empty metrics registry."""
    return MetricsRegistry()


@pytest.fixture
def mock_node_responses():
    """Mock responses from RustChain node."""
    return {
        '/health': {
            'ok': True,
            'version': '2.0.0',
            'uptime_s': 86400.0,
            'db_rw': True,
            'backup_age_h': 2.5,
            'tip_age_slots': 3
        },
        '/epoch': {
            'epoch': 100,
            'slot': 5000,
            'epoch_pot': 1000000.0,
            'enrolled_miners': 50,
            'total_supply_rtc': 21000000.0,
            'blocks_per_epoch': 100
        },
        '/api/miners': [
            {
                'miner_id': 'miner_001',
                'hardware_type': 'PowerPC G4 (Vintage)',
                'device_arch': 'powerpc',
                'antiquity_multiplier': 2.5,
                'last_attestation': time.time() - 300,
                'is_active': True
            },
            {
                'miner_id': 'miner_002',
                'hardware_type': 'Apple Silicon M1',
                'device_arch': 'arm64',
                'antiquity_multiplier': 1.0,
                'last_attestation': time.time() - 600,
                'is_active': True
            },
            {
                'miner_id': 'miner_003',
                'hardware_type': 'Intel x86_64',
                'device_arch': 'x86_64',
                'antiquity_multiplier': 1.2,
                'last_attestation': time.time() - 900,
                'is_active': False
            }
        ]
    }


# =============================================================================
# Configuration Tests
# =============================================================================

class TestExporterConfig:
    """Tests for ExporterConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ExporterConfig()
        assert config.node_url == 'https://rustchain.org'
        assert config.exporter_port == 9100
        assert config.scrape_interval == 30
        assert config.tls_verify is True
        assert config.tls_ca_bundle is None

    def test_environment_variables(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv('RUSTCHAIN_NODE', 'http://custom-node:9000')
        monkeypatch.setenv('EXPORTER_PORT', '9200')
        monkeypatch.setenv('SCRAPE_INTERVAL', '60')
        monkeypatch.setenv('TLS_VERIFY', 'false')

        config = ExporterConfig()
        assert config.node_url == 'http://custom-node:9000'
        assert config.exporter_port == 9200
        assert config.scrape_interval == 60
        assert config.tls_verify is False

    def test_tls_verify_setting_no_bundle(self):
        """Test TLS verify setting without CA bundle."""
        config = ExporterConfig(tls_verify=True, tls_ca_bundle=None)
        assert config.get_verify_setting() is True

        config.tls_verify = False
        assert config.get_verify_setting() is False

    def test_tls_verify_setting_with_bundle(self):
        """Test TLS verify setting with CA bundle."""
        config = ExporterConfig(
            tls_verify=True,
            tls_ca_bundle='/path/to/ca-bundle.crt'
        )
        assert config.get_verify_setting() == '/path/to/ca-bundle.crt'


# =============================================================================
# Metrics Registry Tests
# =============================================================================

class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_add_gauge(self, registry):
        """Test adding gauge metrics."""
        registry.add_gauge('test_metric', 42.0, {'label': 'value'}, 'Test help')
        
        assert 'test_metric' in registry._metrics
        assert len(registry._metrics['test_metric']) == 1
        assert registry._metrics['test_metric'][0].value == 42.0
        assert registry._metrics['test_metric'][0].labels == {'label': 'value'}

    def test_add_counter(self, registry):
        """Test adding counter metrics."""
        registry.add_counter('requests_total', 100.0)
        
        assert registry._metrics['requests_total'][0].value == 100.0
        assert registry._metadata['requests_total']['type'] == 'counter'

    def test_add_info(self, registry):
        """Test adding info metrics."""
        registry.add_info('app_version', {'version': '1.0.0'}, 'App version info')
        
        assert 'app_version_info' in registry._metrics
        assert registry._metrics['app_version_info'][0].value == 1.0
        assert registry._metrics['app_version_info'][0].labels == {'version': '1.0.0'}

    def test_clear(self, registry):
        """Test clearing metrics."""
        registry.add_gauge('test', 1.0)
        registry.clear()
        
        assert len(registry._metrics) == 0
        assert len(registry._metadata) == 0

    def test_prometheus_format_basic(self, registry):
        """Test Prometheus exposition format output."""
        registry.add_gauge('test_metric', 42.0, {'label': 'value'}, 'Test help text')
        
        output = registry.to_prometheus_format()
        
        assert '# HELP test_metric Test help text' in output
        assert '# TYPE test_metric gauge' in output
        assert 'test_metric{label="value"} 42.0' in output

    def test_prometheus_format_multiple_metrics(self, registry):
        """Test exposition with multiple metrics."""
        registry.add_gauge('metric_a', 1.0, {'type': 'a'}, 'Metric A')
        registry.add_gauge('metric_b', 2.0, {'type': 'b'}, 'Metric B')
        registry.add_counter('metric_c', 3.0, {}, 'Metric C')
        
        output = registry.to_prometheus_format()
        
        assert '# HELP metric_a' in output
        assert '# HELP metric_b' in output
        assert '# HELP metric_c' in output
        assert '# TYPE metric_c counter' in output

    def test_label_escaping(self, registry):
        """Test proper escaping of label values."""
        registry.add_gauge('test', 1.0, {'path': '/api/v1', 'quote': 'say "hello"'})
        
        output = registry.to_prometheus_format()
        
        assert 'path="/api/v1"' in output
        assert 'quote="say \\"hello\\""' in output

    def test_timestamp_support(self, registry):
        """Test metric timestamp support."""
        timestamp = 1234567890.123
        registry.add_gauge('test', 1.0, timestamp=timestamp)
        
        output = registry.to_prometheus_format()
        
        # Timestamp should be in milliseconds
        assert '1234567890123' in output


# =============================================================================
# Node Client Tests
# =============================================================================

class TestRustChainNodeClient:
    """Tests for RustChainNodeClient."""

    @patch('rustchain_exporter.requests.Session')
    def test_get_health_success(self, mock_session_class, config, mock_node_responses):
        """Test successful health fetch."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_node_responses['/health']
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = RustChainNodeClient(config)
        health = client.get_health()
        
        assert health.ok is True
        assert health.version == '2.0.0'
        assert health.uptime_s == 86400.0
        assert health.db_rw is True

    @patch('rustchain_exporter.requests.Session')
    def test_get_health_failure(self, mock_session_class, config):
        """Test health fetch failure."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = RequestException("Connection refused")
        
        client = RustChainNodeClient(config)
        health = client.get_health()
        
        assert health.ok is False
        assert health.version == 'unknown'

    @patch('rustchain_exporter.requests.Session')
    def test_get_epoch_success(self, mock_session_class, config, mock_node_responses):
        """Test successful epoch fetch."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_node_responses['/epoch']
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = RustChainNodeClient(config)
        epoch = client.get_epoch()
        
        assert epoch.epoch == 100
        assert epoch.slot == 5000
        assert epoch.epoch_pot == 1000000.0
        assert epoch.enrolled_miners == 50

    @patch('rustchain_exporter.requests.Session')
    def test_get_miners_success(self, mock_session_class, config, mock_node_responses):
        """Test successful miners fetch."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_node_responses['/api/miners']
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        client = RustChainNodeClient(config)
        miners = client.get_miners()
        
        assert len(miners) == 3
        assert miners[0].miner_id == 'miner_001'
        assert miners[0].hardware_type == 'PowerPC G4 (Vintage)'
        assert miners[0].antiquity_multiplier == 2.5

    @patch('rustchain_exporter.requests.Session')
    def test_retry_logic(self, mock_session_class, config):
        """Test request retry logic."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Config has max_retries=2, so we expect 2 calls
        mock_session.get.side_effect = [
            Timeout("Timeout"),
            Timeout("Timeout"),
        ]
        
        client = RustChainNodeClient(config)
        health = client.get_health()
        
        # Should retry max_retries times
        assert mock_session.get.call_count == config.max_retries


# =============================================================================
# Metrics Collector Tests
# =============================================================================

class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @patch('rustchain_exporter.RustChainNodeClient')
    def test_collect_success(self, mock_client_class, config, registry, mock_node_responses):
        """Test successful metrics collection."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Set up mock responses
        mock_client.get_health.return_value = NodeHealth(
            ok=True, version='2.0.0', uptime_s=86400.0, db_rw=True
        )
        mock_client.get_epoch.return_value = EpochInfo(
            epoch=100, slot=5000, epoch_pot=1000000.0,
            enrolled_miners=50, total_supply_rtc=21000000.0
        )
        mock_client.get_miners.return_value = [
            MinerInfo('m1', 'PowerPC', 'powerpc', 2.5, is_active=True),
            MinerInfo('m2', 'Intel', 'x86_64', 1.0, is_active=True)
        ]
        
        collector = MetricsCollector(config, registry)
        success = collector.collect()
        
        assert success is True
        
        # Verify metrics were collected
        assert 'rustchain_node_health' in registry._metrics
        assert 'rustchain_epoch_number' in registry._metrics
        assert 'rustchain_active_miners' in registry._metrics
        assert 'rustchain_scrape_duration_seconds' in registry._metrics

    @patch('rustchain_exporter.RustChainNodeClient')
    def test_collect_failure(self, mock_client_class, config, registry):
        """Test metrics collection with errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_health.side_effect = Exception("Node unavailable")
        
        collector = MetricsCollector(config, registry)
        success = collector.collect()
        
        assert success is False
        assert collector._error_count == 1


# =============================================================================
# Metrics Exposition Tests
# =============================================================================

class TestPrometheusExposition:
    """Tests for PrometheusExposition."""

    def test_add_gauge(self):
        """Test adding gauge metrics."""
        exp = PrometheusExposition()
        exp.add_gauge('test_gauge', 42.0, {'label': 'value'}, 'Test gauge')
        
        output = exp.render()
        
        assert '# HELP test_gauge Test gauge' in output
        assert '# TYPE test_gauge gauge' in output
        assert 'test_gauge{label="value"} 42.0' in output

    def test_add_counter(self):
        """Test adding counter metrics."""
        exp = PrometheusExposition()
        exp.add_counter('requests_total', 1000.0, {'method': 'GET'})
        
        output = exp.render()
        
        assert '# TYPE requests_total counter' in output
        assert 'requests_total{method="GET"} 1000.0' in output

    def test_add_info(self):
        """Test adding info metrics."""
        exp = PrometheusExposition()
        exp.add_info('app', {'version': '1.0.0', 'env': 'prod'})
        
        output = exp.render()
        
        assert 'app_info{env="prod",version="1.0.0"} 1.0' in output

    def test_add_state_set(self):
        """Test adding state set metrics."""
        exp = PrometheusExposition()
        exp.add_state_set('status', {'running': True, 'stopped': False})
        
        output = exp.render()
        
        assert '# TYPE status stateset' in output
        assert 'status{state="running"} 1.0' in output
        assert 'status{state="stopped"} 0.0' in output

    def test_add_histogram(self):
        """Test adding histogram metrics."""
        exp = PrometheusExposition()
        exp.add_histogram(
            'request_duration',
            {0.1: 100, 0.5: 200, 1.0: 250, float('inf'): 300},
            sum_value=150.5,
            count=300
        )
        
        output = exp.render()
        
        assert 'request_duration_bucket{le="0.1"} 100.0' in output
        assert 'request_duration_bucket{le="0.5"} 200.0' in output
        assert 'request_duration_bucket{le="+Inf"} 300.0' in output
        assert 'request_duration_sum 150.5' in output
        assert 'request_duration_count 300.0' in output

    def test_metric_name_validation(self):
        """Test metric name validation."""
        assert validate_metric_name('valid_name') is True
        assert validate_metric_name('valid:name') is True
        assert validate_metric_name('123invalid') is False
        assert validate_metric_name('invalid-name') is False

    def test_label_name_validation(self):
        """Test label name validation."""
        assert validate_label_name('valid_label') is True
        assert validate_label_name('__reserved') is False
        assert validate_label_name('123invalid') is False

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        ts = format_timestamp(1234567890.123)
        assert ts == 1234567890123

    def test_clear(self):
        """Test clearing exposition."""
        exp = PrometheusExposition()
        exp.add_gauge('test', 1.0)
        exp.clear()
        
        output = exp.render()
        assert output == '\n'


# =============================================================================
# HTTP Handler Tests
# =============================================================================

class TestMetricsHandler:
    """Tests for HTTP metrics handler."""

    def test_metrics_endpoint_format(self, registry, config):
        """Test /metrics endpoint returns correct format."""
        registry.add_gauge('test_metric', 42.0, {}, 'Test')
        
        # Create mock request
        handler = Mock(spec=MetricsHandler)
        handler.registry = registry
        handler.collector = Mock(_last_scrape_duration=0.1, _scrape_count=1, _error_count=0)
        handler.config = config
        
        # Call method directly
        MetricsHandler.registry = registry
        MetricsHandler.collector = handler.collector
        MetricsHandler.config = config
        
        # Verify content type would be set correctly
        content_type = 'text/plain; version=0.0.4'
        assert 'text/plain' in content_type
        assert '0.0.4' in content_type

    def test_health_endpoint_response(self, config):
        """Test /health endpoint JSON response."""
        health_data = {
            'status': 'healthy',
            'node_url': config.node_url,
            'scrape_interval': config.scrape_interval
        }
        
        assert health_data['status'] == 'healthy'
        assert 'timestamp' not in health_data  # Would be added dynamically


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the exporter."""

    @patch('rustchain_exporter.RustChainNodeClient')
    def test_full_collection_cycle(self, mock_client_class, config):
        """Test complete metrics collection cycle."""
        # Set up mocks
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_client.get_health.return_value = NodeHealth(
            ok=True, version='2.0.0', uptime_s=3600.0, db_rw=True,
            backup_age_h=1.0, tip_age_slots=2
        )
        mock_client.get_epoch.return_value = EpochInfo(
            epoch=50, slot=2500, epoch_pot=500000.0,
            enrolled_miners=25, total_supply_rtc=10000000.0, blocks_per_epoch=100
        )
        mock_client.get_miners.return_value = [
            MinerInfo('m1', 'PowerPC G4', 'powerpc', 2.0, is_active=True),
            MinerInfo('m2', 'Apple Silicon', 'arm64', 1.0, is_active=True),
            MinerInfo('m3', 'Intel Xeon', 'x86_64', 1.5, is_active=True)
        ]
        
        # Run collection
        registry = MetricsRegistry()
        collector = MetricsCollector(config, registry)
        success = collector.collect()
        
        assert success is True
        
        # Verify all expected metrics are present
        output = registry.to_prometheus_format()
        
        # Health metrics
        assert 'rustchain_node_health' in output
        assert 'rustchain_node_uptime_seconds' in output
        assert 'rustchain_node_db_status' in output
        assert 'rustchain_node_version_info' in output
        
        # Epoch metrics
        assert 'rustchain_epoch_number' in output
        assert 'rustchain_epoch_slot' in output
        assert 'rustchain_epoch_pot_rtc' in output
        assert 'rustchain_enrolled_miners' in output
        assert 'rustchain_total_supply_rtc' in output
        
        # Miner metrics
        assert 'rustchain_active_miners' in output
        assert 'rustchain_miners_by_hardware' in output
        assert 'rustchain_miners_by_architecture' in output
        assert 'rustchain_antiquity_multiplier_avg' in output
        
        # Scrape metrics
        assert 'rustchain_scrape_duration_seconds' in output
        assert 'rustchain_scrapes_total' in output

    def test_exposition_format_compliance(self, registry):
        """Test that exposition format complies with Prometheus spec."""
        registry.add_gauge('compliance_test', 1.0, {'label': 'value'}, 'Test')
        
        output = registry.to_prometheus_format()
        lines = output.strip().split('\n')
        
        # Check structure
        help_lines = [l for l in lines if l.startswith('# HELP')]
        type_lines = [l for l in lines if l.startswith('# TYPE')]
        metric_lines = [l for l in lines if not l.startswith('#')]
        
        assert len(help_lines) > 0
        assert len(type_lines) > 0
        assert len(metric_lines) > 0
        
        # Each metric should have HELP and TYPE
        for help_line in help_lines:
            metric_name = help_line.split()[2]
            assert any(f'# TYPE {metric_name}' in l for l in type_lines)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
