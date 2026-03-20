# SPDX-License-Identifier: MIT
"""
Tests for the RustChain network status generator.
Tests network health checks, miner data parsing, epoch info, HTML generation, and error handling.
"""
import json
import pytest
import sqlite3
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timezone
import tempfile
import os

from network_status_generator import (
    NetworkStatusGenerator,
    fetch_node_health,
    fetch_miners_data,
    fetch_epoch_info,
    generate_status_html,
    main
)


def mock_response(data, status_code=200, ok=True):
    """Create mock HTTP response"""
    response = MagicMock()
    response.status_code = status_code
    response.ok = ok
    response.json.return_value = data
    response.text = json.dumps(data) if isinstance(data, dict) else str(data)
    return response


class TestNetworkStatusGenerator:

    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize test database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                miner_id TEXT,
                hash TEXT,
                epoch INTEGER
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS miners (
                miner_id TEXT PRIMARY KEY,
                wallet_address TEXT,
                hardware_type TEXT,
                last_seen INTEGER,
                total_blocks INTEGER
            )''')
            # Insert test data
            cursor.execute('INSERT INTO blocks VALUES (1, 1700000000, "test_miner_1", "hash123", 100)')
            cursor.execute('INSERT INTO miners VALUES ("test_miner_1", "wallet123", "PowerPC G4", 1700000000, 5)')
            conn.commit()

        self.generator = NetworkStatusGenerator(self.db_path)

    def teardown_method(self):
        os.unlink(self.db_path)

    @patch('network_status_generator.requests.get')
    def test_fetch_node_health_success(self, mock_get):
        health_data = {
            "status": "healthy",
            "uptime": 86400,
            "last_block": 12345,
            "peer_count": 8,
            "sync_status": "synced"
        }
        mock_get.return_value = mock_response(health_data)

        result = fetch_node_health("https://test.node/health")

        assert result == health_data
        mock_get.assert_called_once_with("https://test.node/health", timeout=10, verify=False)

    @patch('network_status_generator.requests.get')
    def test_fetch_node_health_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")

        result = fetch_node_health("https://test.node/health")

        assert result is None

    @patch('network_status_generator.requests.get')
    def test_fetch_miners_data_success(self, mock_get):
        miners_data = {
            "active_miners": [
                {"miner_id": "miner_001", "hardware": "PowerPC G5", "blocks_mined": 150},
                {"miner_id": "miner_002", "hardware": "68K Mac", "blocks_mined": 89}
            ],
            "total_count": 2
        }
        mock_get.return_value = mock_response(miners_data)

        result = fetch_miners_data("https://test.node/api/miners")

        assert result == miners_data
        assert len(result["active_miners"]) == 2

    @patch('network_status_generator.requests.get')
    def test_fetch_epoch_info_success(self, mock_get):
        epoch_data = {
            "current_epoch": 150,
            "epoch_start": 1700000000,
            "blocks_in_epoch": 45,
            "difficulty": "0x1a2b3c"
        }
        mock_get.return_value = mock_response(epoch_data)

        result = fetch_epoch_info("https://test.node/api/epoch")

        assert result["current_epoch"] == 150
        assert result["blocks_in_epoch"] == 45

    def test_get_latest_blocks(self):
        blocks = self.generator.get_latest_blocks(limit=1)

        assert len(blocks) == 1
        assert blocks[0]["miner_id"] == "test_miner_1"
        assert blocks[0]["hash"] == "hash123"

    def test_get_miner_stats(self):
        stats = self.generator.get_miner_stats()

        assert stats["total_miners"] == 1
        assert stats["active_miners"] == 1
        assert "test_miner_1" in [m["miner_id"] for m in stats["miners"]]

    def test_get_network_stats(self):
        with patch.object(self.generator, 'get_latest_blocks') as mock_blocks:
            mock_blocks.return_value = [
                {"timestamp": 1700000000, "epoch": 100},
                {"timestamp": 1699999900, "epoch": 100}
            ]

            stats = self.generator.get_network_stats()

            assert "total_blocks" in stats
            assert "avg_block_time" in stats
            assert "current_epoch" in stats

    def test_generate_status_html_basic(self):
        test_data = {
            "node_health": {"status": "healthy", "uptime": 3600},
            "miners_data": {"active_miners": [], "total_count": 0},
            "epoch_info": {"current_epoch": 100},
            "latest_blocks": [],
            "miner_stats": {"total_miners": 0, "miners": []},
            "network_stats": {"total_blocks": 100, "avg_block_time": 60}
        }

        html = generate_status_html(test_data)

        assert "RustChain Network Status" in html
        assert "healthy" in html
        assert "Current Epoch: 100" in html
        assert "<html>" in html and "</html>" in html

    @patch('network_status_generator.fetch_node_health')
    @patch('network_status_generator.fetch_miners_data')
    @patch('network_status_generator.fetch_epoch_info')
    def test_generate_full_report(self, mock_epoch, mock_miners, mock_health):
        mock_health.return_value = {"status": "healthy", "uptime": 7200}
        mock_miners.return_value = {"active_miners": [], "total_count": 0}
        mock_epoch.return_value = {"current_epoch": 105, "blocks_in_epoch": 23}

        report = self.generator.generate_full_report("https://test.node")

        assert "node_health" in report
        assert "miners_data" in report
        assert "epoch_info" in report
        assert "latest_blocks" in report
        assert report["node_health"]["status"] == "healthy"

    @patch('network_status_generator.fetch_node_health')
    def test_generate_report_with_failed_health_check(self, mock_health):
        mock_health.return_value = None

        report = self.generator.generate_full_report("https://test.node")

        assert report["node_health"] is None

    def test_html_contains_hardware_types(self):
        test_data = {
            "node_health": {"status": "healthy"},
            "miners_data": {
                "active_miners": [
                    {"miner_id": "vintage_1", "hardware": "PowerPC G5", "blocks_mined": 25},
                    {"miner_id": "vintage_2", "hardware": "68K Mac", "blocks_mined": 15}
                ],
                "total_count": 2
            },
            "epoch_info": {"current_epoch": 99},
            "latest_blocks": [],
            "miner_stats": {"total_miners": 2, "miners": []},
            "network_stats": {"total_blocks": 200, "avg_block_time": 45}
        }

        html = generate_status_html(test_data)

        assert "PowerPC G5" in html
        assert "68K Mac" in html
        assert "vintage_1" in html

    def test_html_error_handling(self):
        test_data = {
            "node_health": None,
            "miners_data": None,
            "epoch_info": None,
            "latest_blocks": [],
            "miner_stats": {"total_miners": 0, "miners": []},
            "network_stats": {"total_blocks": 0, "avg_block_time": 0}
        }

        html = generate_status_html(test_data)

        assert "Node Status: Unknown" in html or "Error" in html
        assert "<html>" in html

    @patch('builtins.open', new_callable=mock_open)
    @patch('network_status_generator.NetworkStatusGenerator')
    def test_main_function(self, mock_generator_class, mock_file):
        mock_generator = MagicMock()
        mock_generator.generate_full_report.return_value = {
            "node_health": {"status": "healthy"},
            "latest_blocks": []
        }
        mock_generator_class.return_value = mock_generator

        with patch('network_status_generator.generate_status_html') as mock_html:
            mock_html.return_value = "<html>Test Status Page</html>"

            main()

            mock_generator.generate_full_report.assert_called_once()
            mock_file.assert_called()

    def test_database_connection_error(self):
        with pytest.raises(Exception):
            NetworkStatusGenerator("/nonexistent/path/database.db")

    @patch('network_status_generator.requests.get')
    def test_api_timeout_handling(self, mock_get):
        mock_get.side_effect = Exception("Read timeout")

        result = fetch_miners_data("https://slow.node/api/miners")

        assert result is None

    def test_empty_database_handling(self):
        empty_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        empty_db.close()

        try:
            with sqlite3.connect(empty_db.name) as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE blocks (
                    id INTEGER PRIMARY KEY,
                    timestamp INTEGER,
                    miner_id TEXT,
                    hash TEXT,
                    epoch INTEGER
                )''')
                cursor.execute('''CREATE TABLE miners (
                    miner_id TEXT PRIMARY KEY,
                    wallet_address TEXT,
                    hardware_type TEXT,
                    last_seen INTEGER,
                    total_blocks INTEGER
                )''')
                conn.commit()

            generator = NetworkStatusGenerator(empty_db.name)
            blocks = generator.get_latest_blocks()
            stats = generator.get_miner_stats()

            assert len(blocks) == 0
            assert stats["total_miners"] == 0
        finally:
            os.unlink(empty_db.name)
