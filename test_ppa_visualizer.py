#!/usr/bin/env python3
"""
Tests for PPA Attestation Visualizer
"""

import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ppa_visualizer import generate_radar_chart, generate_hardware_badge, generate_html_report


def test_generate_radar_chart():
    """Test radar chart generation."""
    checks_data = {
        "clock_drift": {"passed": True, "mean_ns": 123456},
        "cache_timing": {"passed": True, "l1_avg": 2.5},
        "simd_identity": {"passed": False},
        "thermal_drift": {"passed": True},
        "instruction_jitter": {"passed": True},
        "anti_emulation": {"passed": True, "emulator_indicators": []},
        "device_age": {"passed": True},
    }
    
    svg = generate_radar_chart(checks_data, 300, 300)
    
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "polygon" in svg
    assert "Clock Drift" in svg
    print("✅ Radar chart test passed")


def test_generate_hardware_badge():
    """Test hardware badge generation."""
    fingerprint_data = {
        "device": {
            "device_family": "PowerPC",
            "device_arch": "power8",
            "cores": 8
        }
    }
    
    svg = generate_hardware_badge(fingerprint_data, 400, 200)
    
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "PowerPC" in svg
    assert "POWER8" in svg
    assert "8 Cores" in svg
    print("✅ Hardware badge test passed")


def test_generate_html_report():
    """Test full HTML report generation."""
    fingerprint_data = {
        "miner": "test-miner",
        "device": {
            "device_family": "x86_64",
            "device_arch": "zen3",
            "cores": 16
        },
        "fingerprint": {
            "checks": {
                "clock_drift": {"passed": True},
                "cache_timing": {"passed": True},
                "simd_identity": {"passed": True},
                "thermal_drift": {"passed": False},
                "instruction_jitter": {"passed": True},
                "anti_emulation": {"passed": True, "emulator_indicators": []},
                "device_age": {"passed": True},
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        temp_path = f.name
    
    generate_html_report(fingerprint_data, temp_path)
    
    with open(temp_path, 'r') as f:
        html = f.read()
    
    assert "<!DOCTYPE html>" in html
    assert "PPA ATTESTATION" in html
    assert "x86_64" in html
    assert "ZEN3" in html
    assert "86%" in html or "6/7" in html  # Score display
    
    Path(temp_path).unlink()
    print("✅ HTML report test passed")


def test_cli_help():
    """Test CLI help output."""
    import subprocess
    result = subprocess.run([sys.executable, 'ppa_visualizer.py', '--help'], 
                          capture_output=True, text=True)
    assert result.returncode == 0
    assert "PPA Attestation Visualizer" in result.stdout
    print("✅ CLI help test passed")


if __name__ == '__main__':
    print("Running PPA Visualizer Tests...\n")
    
    test_generate_radar_chart()
    test_generate_hardware_badge()
    test_generate_html_report()
    test_cli_help()
    
    print("\n🎉 All tests passed!")
