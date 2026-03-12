#!/usr/bin/env python3
"""
Tests for RustChain Node Health Monitor CLI
"""

import json
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from node_health import (
    HealthStatus, EpochStatus, ReachabilityStatus, CheckResult,
    fetch_json, check_health, check_epoch, check_reachability,
    run_checks, format_text, format_json, format_uptime,
    EXIT_OK, EXIT_HEALTH_FAIL, EXIT_EPOCH_FAIL, EXIT_REACHABILITY_FAIL, EXIT_MULTI_FAIL
)


class TestHealthStatus(unittest.TestCase):
    """Test HealthStatus dataclass"""
    
    def test_health_status_ok(self):
        """Test healthy node status"""
        status = HealthStatus(
            ok=True,
            version="2.2.1",
            uptime_s=3600,
            db_rw=True,
            backup_age_hours=1.5,
            tip_age_slots=2,
            error=None
        )
        self.assertTrue(status.ok)
        self.assertEqual(status.version, "2.2.1")
        self.assertEqual(status.uptime_s, 3600)
        self.assertIsNone(status.error)
    
    def test_health_status_error(self):
        """Test unhealthy node status"""
        status = HealthStatus(
            ok=False,
            version=None,
            uptime_s=None,
            db_rw=None,
            backup_age_hours=None,
            tip_age_slots=None,
            error="Connection timeout"
        )
        self.assertFalse(status.ok)
        self.assertEqual(status.error, "Connection timeout")


class TestEpochStatus(unittest.TestCase):
    """Test EpochStatus dataclass"""
    
    def test_epoch_status_ok(self):
        """Test valid epoch status"""
        status = EpochStatus(
            epoch=1234,
            slot=567,
            epoch_pot=1.5,
            enrolled_miners=42,
            blocks_per_epoch=600,
            total_supply_rtc=1000000.0,
            error=None
        )
        self.assertEqual(status.epoch, 1234)
        self.assertEqual(status.slot, 567)
        self.assertEqual(status.enrolled_miners, 42)
    
    def test_epoch_status_error(self):
        """Test epoch status with error"""
        status = EpochStatus(
            epoch=None,
            slot=None,
            epoch_pot=None,
            enrolled_miners=None,
            blocks_per_epoch=None,
            total_supply_rtc=None,
            error="Endpoint unavailable"
        )
        self.assertIsNone(status.epoch)
        self.assertEqual(status.error, "Endpoint unavailable")


class TestReachabilityStatus(unittest.TestCase):
    """Test ReachabilityStatus dataclass"""
    
    def test_reachable_endpoint(self):
        """Test reachable endpoint"""
        status = ReachabilityStatus(
            endpoint="/health",
            reachable=True,
            latency_ms=45.2,
            status_code=200,
            error=None
        )
        self.assertTrue(status.reachable)
        self.assertEqual(status.latency_ms, 45.2)
        self.assertEqual(status.status_code, 200)
    
    def test_unreachable_endpoint(self):
        """Test unreachable endpoint"""
        status = ReachabilityStatus(
            endpoint="/api/miners",
            reachable=False,
            latency_ms=5000.0,
            status_code=None,
            error="Connection refused"
        )
        self.assertFalse(status.reachable)
        self.assertEqual(status.error, "Connection refused")


class TestFormatUptime(unittest.TestCase):
    """Test uptime formatting"""
    
    def test_uptime_seconds(self):
        """Test uptime in seconds"""
        self.assertEqual(format_uptime(120), "2m")
    
    def test_uptime_minutes(self):
        """Test uptime in minutes"""
        self.assertEqual(format_uptime(3660), "1h 1m")
    
    def test_uptime_hours(self):
        """Test uptime in hours"""
        self.assertEqual(format_uptime(90060), "1d 1h 1m")
    
    def test_uptime_none(self):
        """Test None uptime"""
        self.assertEqual(format_uptime(None), "N/A")
    
    def test_uptime_zero(self):
        """Test zero uptime"""
        self.assertEqual(format_uptime(0), "0m")


class TestFormatText(unittest.TestCase):
    """Test text formatting"""
    
    def test_format_text_all_ok(self):
        """Test text formatting when all checks pass"""
        result = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=True, version="2.2.1", uptime_s=3600,
                               db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                                  status_code=200, error=None)
            ],
            overall_ok=True,
            exit_code=EXIT_OK
        )
        
        output = format_text(result)
        self.assertIn("RustChain Node Health Check", output)
        self.assertIn("STATUS: ALL CHECKS PASSED", output)
        self.assertIn("EXIT CODE: 0", output)
    
    def test_format_text_health_fail(self):
        """Test text formatting when health check fails"""
        result = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=False, version=None, uptime_s=None,
                               db_rw=None, backup_age_hours=None, tip_age_slots=None,
                               error="Connection refused"),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=False, latency_ms=1000.0,
                                  status_code=None, error="Connection refused")
            ],
            overall_ok=False,
            exit_code=EXIT_HEALTH_FAIL
        )
        
        output = format_text(result)
        self.assertIn("STATUS: CHECKS FAILED", output)
        self.assertIn("Health check failed", output)


class TestFormatJson(unittest.TestCase):
    """Test JSON formatting"""
    
    def test_format_json_valid(self):
        """Test JSON formatting produces valid JSON"""
        result = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=True, version="2.2.1", uptime_s=3600,
                               db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                                  status_code=200, error=None)
            ],
            overall_ok=True,
            exit_code=EXIT_OK
        )
        
        output = format_json(result)
        data = json.loads(output)  # Should not raise
        
        self.assertEqual(data["node_url"], "https://rustchain.org")
        self.assertEqual(data["exit_code"], 0)
        self.assertTrue(data["overall_ok"])
        self.assertEqual(data["health"]["version"], "2.2.1")


class TestCheckFunctions(unittest.TestCase):
    """Test check functions with mocked responses"""
    
    @patch('node_health.urlopen')
    def test_check_health_success(self, mock_urlopen):
        """Test health check with successful response"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 3600,
            "db_rw": True,
            "backup_age_hours": 1.0,
            "tip_age_slots": 1
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        result = check_health("https://rustchain.org", timeout=10)
        
        self.assertTrue(result.ok)
        self.assertEqual(result.version, "2.2.1")
        self.assertEqual(result.uptime_s, 3600)
        self.assertIsNone(result.error)
    
    @patch('node_health.urlopen')
    def test_check_health_failure(self, mock_urlopen):
        """Test health check with connection error"""
        mock_urlopen.side_effect = URLError("Connection refused")
        
        result = check_health("https://rustchain.org", timeout=10)
        
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertIn("Connection refused", result.error)
    
    @patch('node_health.urlopen')
    def test_check_epoch_success(self, mock_urlopen):
        """Test epoch check with successful response"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "epoch": 1234,
            "slot": 567,
            "epoch_pot": 1.5,
            "enrolled_miners": 42,
            "blocks_per_epoch": 600,
            "total_supply_rtc": 1000000.0
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        result = check_epoch("https://rustchain.org", timeout=10)
        
        self.assertEqual(result.epoch, 1234)
        self.assertEqual(result.slot, 567)
        self.assertEqual(result.enrolled_miners, 42)
        self.assertIsNone(result.error)
    
    @patch('node_health.urlopen')
    def test_check_reachability(self, mock_urlopen):
        """Test reachability check"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        results = check_reachability(
            "https://rustchain.org",
            ["/health", "/epoch"],
            timeout=10
        )
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.reachable for r in results))


class TestRunChecks(unittest.TestCase):
    """Test integrated check runner"""
    
    @patch('node_health.check_health')
    @patch('node_health.check_epoch')
    @patch('node_health.check_reachability')
    def test_run_checks_all_pass(self, mock_reach, mock_epoch, mock_health):
        """Test when all checks pass"""
        mock_health.return_value = HealthStatus(
            ok=True, version="2.2.1", uptime_s=3600,
            db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None
        )
        mock_epoch.return_value = EpochStatus(
            epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
            blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None
        )
        mock_reach.return_value = [
            ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                              status_code=200, error=None)
        ]
        
        result = run_checks("https://rustchain.org", timeout=10)
        
        self.assertTrue(result.overall_ok)
        self.assertEqual(result.exit_code, EXIT_OK)
    
    @patch('node_health.check_health')
    @patch('node_health.check_epoch')
    @patch('node_health.check_reachability')
    def test_run_checks_health_fail(self, mock_reach, mock_epoch, mock_health):
        """Test when only health check fails (node reports unhealthy but reachable)"""
        mock_health.return_value = HealthStatus(
            ok=False, version="2.2.1", uptime_s=3600,
            db_rw=False, backup_age_hours=1.0, tip_age_slots=1,
            error=None  # No error, just unhealthy status
        )
        mock_epoch.return_value = EpochStatus(
            epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
            blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None
        )
        mock_reach.return_value = [
            ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                              status_code=503, error=None)  # Reachable but returns 503
        ]
        
        result = run_checks("https://rustchain.org", timeout=10)
        
        self.assertFalse(result.overall_ok)
        self.assertEqual(result.exit_code, EXIT_HEALTH_FAIL)
    
    @patch('node_health.check_health')
    @patch('node_health.check_epoch')
    @patch('node_health.check_reachability')
    def test_run_checks_multiple_fail(self, mock_reach, mock_epoch, mock_health):
        """Test when multiple checks fail"""
        mock_health.return_value = HealthStatus(
            ok=False, version=None, uptime_s=None,
            db_rw=None, backup_age_hours=None, tip_age_slots=None,
            error="Node unreachable"
        )
        mock_epoch.return_value = EpochStatus(
            epoch=None, slot=None, epoch_pot=None, enrolled_miners=None,
            blocks_per_epoch=None, total_supply_rtc=None,
            error="Epoch endpoint unavailable"
        )
        mock_reach.return_value = [
            ReachabilityStatus(endpoint="/health", reachable=False, latency_ms=1000.0,
                              status_code=None, error="Connection refused")
        ]
        
        result = run_checks("https://rustchain.org", timeout=10)
        
        self.assertFalse(result.overall_ok)
        self.assertEqual(result.exit_code, EXIT_MULTI_FAIL)


class TestMainFunction(unittest.TestCase):
    """Test main CLI entry point"""
    
    @patch('node_health.run_checks')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_text_output(self, mock_stdout, mock_run):
        """Test main function with text output"""
        mock_run.return_value = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=True, version="2.2.1", uptime_s=3600,
                               db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                                  status_code=200, error=None)
            ],
            overall_ok=True,
            exit_code=EXIT_OK
        )
        
        from node_health import main
        exit_code = main(["-n", "https://rustchain.org"])
        
        self.assertEqual(exit_code, EXIT_OK)
        output = mock_stdout.getvalue()
        self.assertIn("RustChain Node Health Check", output)
    
    @patch('node_health.run_checks')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_json_output(self, mock_stdout, mock_run):
        """Test main function with JSON output"""
        mock_run.return_value = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=True, version="2.2.1", uptime_s=3600,
                               db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                                  status_code=200, error=None)
            ],
            overall_ok=True,
            exit_code=EXIT_OK
        )
        
        from node_health import main
        exit_code = main(["-n", "https://rustchain.org", "--json"])
        
        self.assertEqual(exit_code, EXIT_OK)
        output = mock_stdout.getvalue()
        data = json.loads(output)  # Should be valid JSON
        self.assertEqual(data["exit_code"], 0)
    
    @patch('node_health.run_checks')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_quiet_mode(self, mock_stdout, mock_run):
        """Test main function in quiet mode"""
        mock_run.return_value = CheckResult(
            node_url="https://rustchain.org",
            timestamp="2024-01-01T00:00:00Z",
            health=HealthStatus(ok=True, version="2.2.1", uptime_s=3600,
                               db_rw=True, backup_age_hours=1.0, tip_age_slots=1, error=None),
            epoch=EpochStatus(epoch=100, slot=50, epoch_pot=1.5, enrolled_miners=10,
                             blocks_per_epoch=600, total_supply_rtc=1000000.0, error=None),
            reachability=[
                ReachabilityStatus(endpoint="/health", reachable=True, latency_ms=50.0,
                                  status_code=200, error=None)
            ],
            overall_ok=True,
            exit_code=EXIT_OK
        )
        
        from node_health import main
        exit_code = main(["-n", "https://rustchain.org", "-q"])
        
        self.assertEqual(exit_code, EXIT_OK)
        self.assertEqual(mock_stdout.getvalue(), "")  # No output in quiet mode


if __name__ == "__main__":
    unittest.main()
