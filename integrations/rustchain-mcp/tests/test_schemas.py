#!/usr/bin/env python3
"""
RustChain MCP - Test Suite

Unit tests for schemas, client, and MCP server.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Import test targets
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from rustchain_mcp.schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        MinerInfo,
        NetworkStats,
        QueryResult,
        WalletBalance,
    )
except ImportError:
    from schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        MinerInfo,
        NetworkStats,
        QueryResult,
        WalletBalance,
    )


class TestHealthStatus:
    """Tests for HealthStatus schema."""

    def test_from_dict_minimal(self):
        """Test creating HealthStatus from minimal dict."""
        data = {"status": "ok", "timestamp": 1234567890, "service": "test"}
        health = HealthStatus.from_dict(data)
        
        assert health.status == "ok"
        assert health.timestamp == 1234567890
        assert health.service == "test"
        assert health.version is None
        assert health.uptime_s is None

    def test_from_dict_full(self):
        """Test creating HealthStatus from full dict."""
        data = {
            "status": "ok",
            "timestamp": 1234567890,
            "service": "beacon-api",
            "version": "2.2.1",
            "uptime_s": 86400,
        }
        health = HealthStatus.from_dict(data)
        
        assert health.version == "2.2.1"
        assert health.uptime_s == 86400

    def test_is_healthy_true(self):
        """Test is_healthy property for healthy status."""
        for status in ["ok", "OK", "healthy", "running"]:
            health = HealthStatus(status=status, timestamp=0, service="test")
            assert health.is_healthy is True

    def test_is_healthy_false(self):
        """Test is_healthy property for unhealthy status."""
        for status in ["error", "down", "unknown"]:
            health = HealthStatus(status=status, timestamp=0, service="test")
            assert health.is_healthy is False


class TestEpochInfo:
    """Tests for EpochInfo schema."""

    def test_from_dict_minimal(self):
        """Test creating EpochInfo from minimal dict."""
        data = {"epoch": 95, "slot": 12345, "height": 67890}
        epoch = EpochInfo.from_dict(data)
        
        assert epoch.epoch == 95
        assert epoch.slot == 12345
        assert epoch.height == 67890

    def test_from_dict_full(self):
        """Test creating EpochInfo from full dict."""
        data = {
            "epoch": 95,
            "slot": 12345,
            "height": 67890,
            "start_time": 1234567890,
            "end_time": 1234568490,
            "active_miners": 150,
            "total_rewards": 1000.0,
            "status": "active",
        }
        epoch = EpochInfo.from_dict(data)
        
        assert epoch.start_time == 1234567890
        assert epoch.active_miners == 150
        assert epoch.total_rewards == 1000.0
        assert epoch.status == "active"


class TestWalletBalance:
    """Tests for WalletBalance schema."""

    def test_from_dict_minimal(self):
        """Test creating WalletBalance from minimal dict."""
        data = {"miner_id": "scott", "amount_rtc": 155.0, "amount_i64": 155000000}
        balance = WalletBalance.from_dict(data)
        
        assert balance.miner_id == "scott"
        assert balance.amount_rtc == 155.0
        assert balance.amount_i64 == 155000000

    def test_total_rtc_with_staked(self):
        """Test total_rtc property includes staked."""
        balance = WalletBalance(
            miner_id="test",
            amount_rtc=100.0,
            amount_i64=100000000,
            staked=50.0,
        )
        assert balance.total_rtc == 150.0

    def test_total_rtc_no_staked(self):
        """Test total_rtc property with no staked."""
        balance = WalletBalance(
            miner_id="test",
            amount_rtc=100.0,
            amount_i64=100000000,
        )
        assert balance.total_rtc == 100.0


class TestQueryResult:
    """Tests for QueryResult schema."""

    def test_from_dict_success(self):
        """Test creating QueryResult from success response."""
        data = {
            "success": True,
            "data": {"miners": []},
            "count": 0,
            "query_type": "miners",
        }
        result = QueryResult.from_dict(data)
        
        assert result.success is True
        assert result.count == 0
        assert result.query_type == "miners"

    def test_from_dict_error(self):
        """Test creating QueryResult from error response."""
        data = {
            "success": False,
            "error": "Invalid query type",
        }
        result = QueryResult.from_dict(data)
        
        assert result.success is False
        assert result.error == "Invalid query type"


class TestMinerInfo:
    """Tests for MinerInfo schema."""

    def test_from_dict(self):
        """Test creating MinerInfo from dict."""
        data = {
            "miner_id": "miner_123",
            "wallet": "wallet_xyz",
            "hardware": "PowerPC G4",
            "score": 245.8,
            "epochs_mined": 1250,
            "last_seen": 1234567890,
            "status": "active",
            "antiquity_multiplier": 2.5,
        }
        miner = MinerInfo.from_dict(data)
        
        assert miner.miner_id == "miner_123"
        assert miner.hardware == "PowerPC G4"
        assert miner.score == 245.8
        assert miner.antiquity_multiplier == 2.5


class TestNetworkStats:
    """Tests for NetworkStats schema."""

    def test_from_dict(self):
        """Test creating NetworkStats from dict."""
        data = {
            "current_epoch": 95,
            "total_miners": 500,
            "active_miners": 150,
            "total_supply": 1000000.0,
        }
        stats = NetworkStats.from_dict(data)
        
        assert stats.current_epoch == 95
        assert stats.total_miners == 500
        assert stats.active_miners == 150


class TestAPIError:
    """Tests for APIError schema."""

    def test_from_response(self):
        """Test creating APIError from response."""
        body = {"error": "NOT_FOUND", "message": "Miner not found"}
        error = APIError.from_response(404, body)
        
        assert error.code == "NOT_FOUND"
        assert error.message == "Miner not found"
        assert error.status_code == 404

    def test_to_dict(self):
        """Test converting APIError to dict."""
        error = APIError(
            code="TEST_ERROR",
            message="Test message",
            status_code=500,
            details={"key": "value"},
        )
        result = error.to_dict()
        
        assert result["error"] == "TEST_ERROR"
        assert result["message"] == "Test message"
        assert result["details"] == {"key": "value"}
