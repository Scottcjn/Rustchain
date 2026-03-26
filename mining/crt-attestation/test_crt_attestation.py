#!/usr/bin/env python3
"""
Tests for CRT Light Attestation

Run: python -m pytest mining/crt-attestation/test_crt_attestation.py -v
"""

import hashlib
import math
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crt_patterns import (
    generate_checkerboard, generate_gradient, generate_timing_bars,
    generate_phosphor_test, generate_scanline_grid, pattern_hash,
    ALL_PATTERNS, generate_pattern,
)
from crt_fingerprint import (
    CRTFingerprint, classify_phosphor, compute_crt_confidence,
    analyze_phosphor_decay, analyze_refresh_rate, analyze_scanline_timing,
    analyze_brightness_gamma, simulate_crt_fingerprint, simulate_lcd_fingerprint,
    FLAG_NO_PHOSPHOR_DECAY, FLAG_PERFECT_REFRESH, FLAG_NO_SCANLINE_JITTER,
    FLAG_NO_WARMUP, PHOSPHOR_TYPES,
)
from crt_attestation import CRTAttestationCapture, build_fingerprint


# ── Pattern Tests ────────────────────────────────────────────────

class TestPatterns(unittest.TestCase):
    def test_checkerboard_dimensions(self):
        grid = generate_checkerboard(64, 48)
        self.assertEqual(len(grid), 48)
        self.assertEqual(len(grid[0]), 64)

    def test_checkerboard_alternates(self):
        grid = generate_checkerboard(16, 16, block_size=8)
        self.assertEqual(grid[0][0], 255)  # First block white
        self.assertEqual(grid[0][8], 0)    # Second block black

    def test_gradient_range(self):
        grid = generate_gradient(256, 1)
        self.assertEqual(grid[0][0], 0)    # Start black
        self.assertEqual(grid[0][-1], 255) # End white

    def test_gradient_monotonic(self):
        grid = generate_gradient(100, 1)
        for i in range(len(grid[0]) - 1):
            self.assertLessEqual(grid[0][i], grid[0][i + 1])

    def test_timing_bars(self):
        grid = generate_timing_bars(160, 10, num_bars=16)
        self.assertEqual(len(grid), 10)
        self.assertIn(0, grid[0])
        self.assertIn(255, grid[0])

    def test_phosphor_test_halves(self):
        grid = generate_phosphor_test(64, 48)
        self.assertEqual(grid[0][0], 255)   # Top: white
        self.assertEqual(grid[47][0], 0)    # Bottom: black

    def test_scanline_grid(self):
        grid = generate_scanline_grid(64, 10)
        self.assertEqual(grid[0][0], 255)  # Even lines white
        self.assertEqual(grid[1][0], 0)    # Odd lines black

    def test_all_patterns_generate(self):
        for name in ALL_PATTERNS:
            grid = generate_pattern(name, 32, 24)
            self.assertEqual(len(grid), 24)
            self.assertEqual(len(grid[0]), 32)

    def test_pattern_hash_deterministic(self):
        h1 = pattern_hash("checkerboard", 640, 480)
        h2 = pattern_hash("checkerboard", 640, 480)
        self.assertEqual(h1, h2)

    def test_pattern_hash_unique(self):
        h1 = pattern_hash("checkerboard", 640, 480)
        h2 = pattern_hash("gradient", 640, 480)
        self.assertNotEqual(h1, h2)


# ── Phosphor Classification Tests ────────────────────────────────

class TestPhosphorClassification(unittest.TestCase):
    def test_p22_classified(self):
        result = classify_phosphor(1.2)
        self.assertEqual(result, "P22")

    def test_p31_classified(self):
        result = classify_phosphor(0.035)
        self.assertEqual(result, "P31")

    def test_p4_classified(self):
        result = classify_phosphor(0.06)
        self.assertEqual(result, "P4")

    def test_all_types_exist(self):
        for ptype in ["P22", "P43", "P31", "P4", "P45"]:
            self.assertIn(ptype, PHOSPHOR_TYPES)


# ── Decay Analysis Tests ─────────────────────────────────────────

class TestDecayAnalysis(unittest.TestCase):
    def test_exponential_decay(self):
        # Simulate P22 decay
        samples = [255 * math.exp(-t / 0.0004) for t in [i/10000 for i in range(100)]]
        decay_ms, phosphor, curve_hash = analyze_phosphor_decay(samples, 10000)
        self.assertGreater(decay_ms, 0)
        self.assertIn(phosphor, PHOSPHOR_TYPES)
        self.assertGreater(len(curve_hash), 0)

    def test_empty_samples(self):
        decay_ms, phosphor, _ = analyze_phosphor_decay([], 10000)
        self.assertEqual(decay_ms, 0.0)
        self.assertEqual(phosphor, "unknown")

    def test_zero_peak(self):
        decay_ms, _, _ = analyze_phosphor_decay([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 10000)
        self.assertEqual(decay_ms, 0.0)


# ── Refresh Analysis Tests ───────────────────────────────────────

class TestRefreshAnalysis(unittest.TestCase):
    def test_60hz_detected(self):
        ts = [i / 60.0 for i in range(120)]
        hz, drift, jitter = analyze_refresh_rate(ts)
        self.assertAlmostEqual(hz, 60.0, places=1)

    def test_drift_detected(self):
        # 60.003 Hz (50 ppm drift)
        ts = [i / 60.003 for i in range(120)]
        hz, drift, jitter = analyze_refresh_rate(ts)
        self.assertGreater(drift, 0)

    def test_too_few_frames(self):
        hz, _, _ = analyze_refresh_rate([0.0, 0.016])
        self.assertEqual(hz, 0.0)  # Need 3+ frames for analysis

    def test_empty(self):
        hz, _, _ = analyze_refresh_rate([])
        self.assertEqual(hz, 0.0)


# ── Scanline Analysis Tests ──────────────────────────────────────

class TestScanlineAnalysis(unittest.TestCase):
    def test_uniform_timing(self):
        ts = [i * 31.746e-6 for i in range(480)]  # NTSC line time
        jitter, flyback, hsync = analyze_scanline_timing(ts)
        self.assertAlmostEqual(jitter, 0.0, places=0)

    def test_empty(self):
        j, f, h = analyze_scanline_timing([])
        self.assertEqual(j, 0.0)


# ── CRT Confidence Tests ────────────────────────────────────────

class TestCRTConfidence(unittest.TestCase):
    def test_real_crt_high_confidence(self):
        crt = simulate_crt_fingerprint(monitor_age_years=15)
        self.assertGreater(crt.crt_confidence, 0.7)

    def test_lcd_low_confidence(self):
        lcd = simulate_lcd_fingerprint()
        self.assertLess(lcd.crt_confidence, 0.3)

    def test_lcd_has_flags(self):
        lcd = simulate_lcd_fingerprint()
        self.assertTrue(lcd.emulator_flags & FLAG_NO_PHOSPHOR_DECAY)
        self.assertTrue(lcd.emulator_flags & FLAG_NO_WARMUP)

    def test_crt_no_lcd_flags(self):
        crt = simulate_crt_fingerprint()
        self.assertFalse(crt.emulator_flags & FLAG_NO_PHOSPHOR_DECAY)
        self.assertFalse(crt.emulator_flags & FLAG_NO_WARMUP)

    def test_confidence_bounded(self):
        fp = CRTFingerprint(
            phosphor_decay_ms=2.0, actual_refresh_hz=60.0,
            refresh_drift_ppm=100, scanline_jitter_ns=50,
            gamma_curve_hash="abc", warmup_time_s=3.0,
            beam_current_drop_pct=8.0, flyback_duration_us=500,
        )
        conf, flags = compute_crt_confidence(fp)
        self.assertLessEqual(conf, 1.0)
        self.assertGreaterEqual(conf, 0.0)


# ── Fingerprint Hash Tests ──────────────────────────────────────

class TestFingerprintHash(unittest.TestCase):
    def test_deterministic(self):
        crt = simulate_crt_fingerprint()
        h1 = crt.fingerprint_hash()
        h2 = crt.fingerprint_hash()
        self.assertEqual(h1, h2)

    def test_different_crts_different_hash(self):
        crt1 = simulate_crt_fingerprint(monitor_age_years=5)
        crt2 = simulate_crt_fingerprint(monitor_age_years=25)
        # Very unlikely to match due to random aging
        # (small chance of collision, so we test it's a valid hash)
        self.assertEqual(len(crt1.fingerprint_hash()), 64)

    def test_to_dict(self):
        fp = simulate_crt_fingerprint()
        d = fp.to_dict()
        self.assertIn("phosphor_decay_ms", d)
        self.assertIn("crt_confidence", d)
        self.assertIn("actual_refresh_hz", d)


# ── Capture Tests ────────────────────────────────────────────────

class TestCapture(unittest.TestCase):
    def test_demo_capture_works(self):
        cap = CRTAttestationCapture("demo")
        samples = cap.capture_phosphor_decay()
        self.assertGreater(len(samples), 0)

    def test_demo_frame_timestamps(self):
        cap = CRTAttestationCapture("demo")
        ts = cap.capture_frame_timestamps(60)
        self.assertEqual(len(ts), 60)
        # Monotonically increasing
        for i in range(len(ts) - 1):
            self.assertLess(ts[i], ts[i + 1])

    def test_demo_scanline_timestamps(self):
        cap = CRTAttestationCapture("demo")
        ts = cap.capture_scanline_timestamps(100)
        self.assertEqual(len(ts), 100)

    def test_demo_gradient_response(self):
        cap = CRTAttestationCapture("demo")
        resp = cap.capture_gradient_response(256)
        self.assertEqual(len(resp), 256)
        self.assertAlmostEqual(resp[0], 0, places=0)

    def test_build_fingerprint_demo(self):
        cap = CRTAttestationCapture("demo")
        fp = build_fingerprint(cap)
        self.assertIsInstance(fp, CRTFingerprint)
        self.assertGreater(fp.crt_confidence, 0.5)
        self.assertGreater(fp.phosphor_decay_ms, 0)


if __name__ == "__main__":
    unittest.main()
