#!/usr/bin/env python3
"""Unit tests for get_hardware_serial.py"""

import pytest
import platform
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'node'))

from get_hardware_serial import (
    get_hardware_serial,
    get_serial_with_fallback,
    get_mac_serial,
    get_linux_serial,
    get_windows_serial,
    run_cmd
)


class TestRunCmd:
    """Test run_cmd function."""

    def test_run_cmd_with_string(self):
        """Test run_cmd with a simple command string."""
        result = run_cmd('echo test')
        assert result == 'test'

    def test_run_cmd_with_list(self):
        """Test run_cmd with a list of arguments."""
        result = run_cmd(['echo', 'hello'])
        assert result == 'hello'

    def test_run_cmd_invalid_command(self):
        """Test run_cmd with invalid command returns empty string."""
        result = run_cmd('nonexistent_command_12345')
        assert result == ''

    def test_run_cmd_timeout(self):
        """Test run_cmd with command that would timeout."""
        result = run_cmd('sleep 10')
        # Should return empty due to timeout
        assert result == ''


class TestGetHardwareSerial:
    """Test platform-specific serial detection."""

    @patch('get_hardware_serial.platform.system')
    def test_get_hardware_serial_darwin(self, mock_system):
        """Test serial detection on macOS."""
        mock_system.return_value = 'Darwin'
        with patch('get_hardware_serial.get_mac_serial') as mock_mac:
            mock_mac.return_value = 'ABC123456'
            result = get_hardware_serial()
            assert result == 'ABC123456'

    @patch('get_hardware_serial.platform.system')
    def test_get_hardware_serial_linux(self, mock_system):
        """Test serial detection on Linux."""
        mock_system.return_value = 'Linux'
        with patch('get_hardware_serial.get_linux_serial') as mock_linux:
            mock_linux.return_value = 'LINUX123'
            result = get_hardware_serial()
            assert result == 'LINUX123'

    @patch('get_hardware_serial.platform.system')
    def test_get_hardware_serial_windows(self, mock_system):
        """Test serial detection on Windows."""
        mock_system.return_value = 'Windows'
        with patch('get_hardware_serial.get_windows_serial') as mock_win:
            mock_win.return_value = 'WINDOWS456'
            result = get_hardware_serial()
            assert result == 'WINDOWS456'

    @patch('get_hardware_serial.platform.system')
    def test_get_hardware_serial_unknown(self, mock_system):
        """Test serial detection on unknown platform."""
        mock_system.return_value = 'FreeBSD'
        result = get_hardware_serial()
        assert result is None


class TestGetSerialWithFallback:
    """Test fallback serial detection."""

    def test_fallback_returns_tuple(self):
        """Test that fallback returns a tuple of (serial, source)."""
        with patch('get_hardware_serial.get_hardware_serial') as mock_hw:
            mock_hw.return_value = 'TEST123'
            serial, source = get_serial_with_fallback()
            assert serial == 'TEST123'
            assert source == 'hardware'
            assert isinstance(serial, str)
            assert isinstance(source, str)

    def test_fallback_none_values(self):
        """Test fallback when no serial is available."""
        with patch('get_hardware_serial.get_hardware_serial') as mock_hw:
            mock_hw.return_value = None
            with patch('get_hardware_serial.run_cmd') as mock_run:
                mock_run.return_value = ''
                serial, source = get_serial_with_fallback()
                assert serial is None
                assert source == 'none'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
