"""Tests for tools/prometheus-exporter/rustchain_exporter.py"""

import json
import os
import sys
import pytest

# Ensure the exporter module is importable
EXPORTER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(EXPORTER_DIR, "..", "tools", "prometheus-exporter"))

from rustchain_exporter import app, _metrics, _miner_multipliers


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestMetricsEndpoint:
    """Test the /metrics Prometheus endpoint."""

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self, client):
        resp = client.get("/metrics")
        assert "text/plain" in resp.content_type

    def test_metrics_has_node_up(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_node_up" in body

    def test_metrics_has_epoch(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_epoch" in body

    def test_metrics_has_miners_total(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_miners_total" in body

    def test_metrics_has_version_info(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_node_version_info" in body

    def test_metrics_has_last_scrape(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_last_scrape_timestamp" in body

    def test_metrics_has_miner_antiquity_multiplier_header(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "rustchain_miner_antiquity_multiplier" in body


class TestMinerMultipliers:
    """Test per-miner antiquity multiplier rendering."""

    def test_no_miners_still_has_header(self, client):
        _miner_multipliers.clear()
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "# HELP rustchain_miner_antiquity_multiplier" in body

    def test_single_miner_rendered(self, client):
        _miner_multipliers.clear()
        _miner_multipliers["miner_abc123"] = 1.5
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert 'miner="miner_abc123"' in body
        assert "1.5" in body

    def test_multiple_miners_sorted(self, client):
        _miner_multipliers.clear()
        _miner_multipliers["z_miner"] = 2.0
        _miner_multipliers["a_miner"] = 0.5
        resp = client.get("/metrics")
        body = resp.data.decode()
        a_pos = body.index("a_miner")
        z_pos = body.index("z_miner")
        assert a_pos < z_pos, "Miners should be sorted alphabetically"


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert "status" in data

    def test_health_has_exporter_name(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data.get("exporter") == "rustchain-prometheus-exporter"


class TestPrometheusFormat:
    """Verify Prometheus exposition format compliance."""

    def test_has_help_and_type_comments(self, client):
        resp = client.get("/metrics")
        body = resp.data.decode()
        assert "# HELP rustchain_node_up" in body
        assert "# TYPE rustchain_node_up gauge" in body

    def test_valid_gauge_syntax(self, client):
        _metrics["node_up"] = 1
        resp = client.get("/metrics")
        body = resp.data.decode()
        lines = body.strip().split("\n")
        gauge_lines = [
            l for l in lines if l.startswith("rustchain_") and not l.startswith("#")
        ]
        for line in gauge_lines:
            parts = line.split()
            assert len(parts) == 2 or (len(parts) >= 2 and "{" in parts[0]), (
                f"Invalid gauge line: {line}"
            )
