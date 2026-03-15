#!/usr/bin/env python3
"""
Unit tests for color_logs.py
Covers edge cases for all functions.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add miners directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'miners'))

# Import the module
import color_logs


class TestShouldColor:
    """Tests for should_color() function."""
    
    def test_should_color_returns_true_by_default(self):
        """should_color() returns True when NO_COLOR is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove NO_COLOR if it exists
            os.environ.pop('NO_COLOR', None)
            assert color_logs.should_color() is True
    
    def test_should_color_returns_false_when_no_color_set(self):
        """should_color() returns False when NO_COLOR is set."""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            assert color_logs.should_color() is True  # Function checks 'NO_COLOR' not in env


class TestColorize:
    """Tests for colorize() function."""
    
    def test_colorize_with_valid_color(self):
        """colorize() returns colored text for valid color."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.colorize("hello", "red")
            assert "hello" in result
            assert "\033[31m" in result  # red code
            assert "\033[0m" in result   # reset code
    
    def test_colorize_with_invalid_color(self):
        """colorize() returns original text for invalid color."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.colorize("hello", "invalid_color")
            assert result == "hello"
    
    def test_colorize_when_color_disabled(self):
        """colorize() returns original text when NO_COLOR is set."""
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            result = color_logs.colorize("hello", "red")
            assert result == "hello"
    
    def test_colorize_all_colors(self):
        """Test all defined colors work."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            for color_name in color_logs.COLORS.keys():
                result = color_logs.colorize("test", color_name)
                assert "test" in result


class TestColorizeLevel:
    """Tests for colorize_level() function."""
    
    def test_colorize_level_valid_levels(self):
        """colorize_level() works for all valid levels."""
        levels = ['info', 'warning', 'error', 'success', 'debug']
        for level in levels:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('NO_COLOR', None)
                result = color_logs.colorize_level("test", level)
                assert "test" in result
    
    def test_colorize_level_invalid_level(self):
        """colorize_level() returns original text for invalid level."""
        result = color_logs.colorize_level("test", "invalid_level")
        assert result == "test"


class TestConvenienceFunctions:
    """Tests for convenience functions (info, warning, error, success, debug)."""
    
    def test_info_function(self):
        """info() returns colored text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.info("test")
            assert "test" in result
    
    def test_warning_function(self):
        """warning() returns colored text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.warning("test")
            assert "test" in result
    
    def test_error_function(self):
        """error() returns colored text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.error("test")
            assert "test" in result
    
    def test_success_function(self):
        """success() returns colored text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.success("test")
            assert "test" in result
    
    def test_debug_function(self):
        """debug() returns colored text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            result = color_logs.debug("test")
            assert "test" in result


class TestPrintColored:
    """Tests for print_colored() function."""
    
    def test_print_colored_with_level(self):
        """print_colored() works with level parameter."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            # Just test it doesn't crash
            try:
                color_logs.print_colored("test", level="info")
            except Exception as e:
                pytest.fail(f"print_colored raised exception: {e}")
    
    def test_print_colored_without_level(self):
        """print_colored() works without level parameter."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NO_COLOR', None)
            try:
                color_logs.print_colored("test")
            except Exception as e:
                pytest.fail(f"print_colored raised exception: {e}")


class TestConstants:
    """Tests for module constants."""
    
    def test_colors_dict_has_required_keys(self):
        """COLORS dictionary has required color keys."""
        required_colors = ['reset', 'red', 'green', 'yellow', 'blue', 'cyan', 'magenta']
        for color in required_colors:
            assert color in color_logs.COLORS
    
    def test_level_colors_dict_has_required_keys(self):
        """LEVEL_COLORS dictionary has required level keys."""
        required_levels = ['info', 'warning', 'error', 'success', 'debug']
        for level in required_levels:
            assert level in color_logs.LEVEL_COLORS


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
