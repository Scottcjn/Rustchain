#!/usr/bin/env python3
"""
Test script for UniversalMiner JSON mode functionality.

Verifies that the miner correctly handles JSON output vs standard output
based on the json_mode flag.

Usage:
    python3 test_json_output.py

Test cases:
    1. json_mode=True: _emit() outputs JSON, _print() is suppressed
    2. json_mode=False: _print() outputs text, _emit() is suppressed
"""

import sys

# Add current directory to path for imports
sys.path.insert(0, '.')

from deprecated.old_miners.rustchain_universal_miner import UniversalMiner


def test_json_mode_enabled() -> None:
    """
    Test miner with JSON mode enabled.
    
    Expected behavior:
        - _emit() outputs JSON formatted data
        - _print() calls are suppressed (no stdout output)
    """
    print("Testing with json_mode=True...")
    miner = UniversalMiner(miner_id='test-miner', json_mode=True)
    
    # _emit should output JSON
    miner._emit('test', foo='bar', num=123)
    
    # _print should be suppressed
    miner._print('This should not appear')
    print("✓ JSON mode test completed\n")


def test_json_mode_disabled() -> None:
    """
    Test miner with JSON mode disabled (standard text mode).
    
    Expected behavior:
        - _print() outputs text to stdout
        - _emit() calls are suppressed (no JSON output)
    """
    print("Testing with json_mode=False...")
    miner2 = UniversalMiner(miner_id='test-miner', json_mode=False)
    
    # _print should output text
    miner2._print('This should appear')
    
    # _emit should be suppressed
    miner2._emit('test', baz='qux')
    print("✓ Text mode test completed\n")


def main() -> None:
    """
    Run all UniversalMiner JSON mode tests.
    
    Flow:
        1. Test with json_mode=True (JSON output enabled)
        2. Test with json_mode=False (text output enabled)
        3. Print completion message
    """
    print("=" * 60)
    print("UniversalMiner JSON Mode Test Suite")
    print("=" * 60 + "\n")
    
    test_json_mode_enabled()
    test_json_mode_disabled()
    
    print("=" * 60)
    print("Test completed.")
    print("=" * 60)


if __name__ == '__main__':
    main()