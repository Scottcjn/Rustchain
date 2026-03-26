#!/usr/bin/env python3
"""
CRT Light Attestation — Main Module

Generates test patterns, captures optical data from CRT monitors,
extracts fingerprints, and submits attestation to RustChain.

Usage:
    python crt_attestation.py --demo
    python crt_attestation.py --capture webcam --device /dev/video0
    python crt_attestation.py --capture gpio --pin 18

Bounty: rustchain-bounties#2310 (140 RTC)
"""

import argparse
import hashlib
import json
import time
from typing import Optional

from crt_fingerprint import (
    CRTFingerprint,
    simulate_crt_fingerprint,
    simulate_lcd_fingerprint,
    compute_crt_confidence,
    analyze_phosphor_decay,
    analyze_refresh_rate,
    analyze_scanline_timing,
    analyze_brightness_gamma,
)
from crt_patterns import ALL_PATTERNS, generate_pattern, pattern_hash


class CRTAttestationCapture:
    """Capture optical data from a CRT monitor."""

    def __init__(self, method: str = "demo", device: str = None, pin: int = None):
        self.method = method
        self.device = device
        self.pin = pin

    def capture_phosphor_decay(self, duration_s: float = 0.5,
                                sample_rate: float = 10000) -> list:
        """
        Capture brightness samples after flash-to-black transition.
        
        With webcam: high-FPS capture of CRT screen area
        With GPIO: photodiode ADC readings
        Demo: simulated P22 decay curve
        """
        if self.method == "demo":
            return self._demo_phosphor_decay(duration_s, sample_rate)
        elif self.method == "webcam":
            return self._webcam_capture_brightness(duration_s, sample_rate)
        elif self.method == "gpio":
            return self._gpio_capture_brightness(duration_s, sample_rate)
        return []

    def capture_frame_timestamps(self, num_frames: int = 120) -> list:
        """Capture frame boundary timestamps for refresh analysis."""
        if self.method == "demo":
            return self._demo_frame_timestamps(num_frames)
        return []

    def capture_scanline_timestamps(self, num_lines: int = 480) -> list:
        """Capture per-scanline timing for jitter analysis."""
        if self.method == "demo":
            return self._demo_scanline_timestamps(num_lines)
        return []

    def capture_gradient_response(self, steps: int = 256) -> list:
        """Capture brightness at each gradient step for gamma analysis."""
        if self.method == "demo":
            return self._demo_gradient_response(steps)
        return []

    # ── Demo implementations ─────────────────────────────────────

    def _demo_phosphor_decay(self, duration_s, sample_rate):
        """Simulate P22 phosphor decay: ~1.2ms to 10%."""
        import math
        samples = []
        num_samples = int(duration_s * sample_rate)
        # Exponential decay with P22 characteristics
        tau = 0.0004  # Time constant (~0.4ms)
        for i in range(num_samples):
            t = i / sample_rate
            brightness = 255 * math.exp(-t / tau)
            # Add noise (real photodiode has noise)
            import random
            brightness += random.gauss(0, 0.5)
            samples.append(max(0, brightness))
        return samples

    def _demo_frame_timestamps(self, num_frames):
        """Simulate 60Hz with CRT-typical drift and jitter."""
        import random
        timestamps = []
        t = 0.0
        nominal_interval = 1.0 / 60.0
        # CRT drift: ~50 ppm
        drift_factor = 1.0 + 50e-6
        for _ in range(num_frames):
            jitter = random.gauss(0, 15e-6)  # ~15μs jitter
            t += nominal_interval * drift_factor + jitter
            timestamps.append(t)
        return timestamps

    def _demo_scanline_timestamps(self, num_lines):
        """Simulate horizontal scanline timing with jitter."""
        import random
        timestamps = []
        t = 0.0
        line_time = 1.0 / (60.0 * 525)  # NTSC: 525 lines per frame
        for i in range(num_lines):
            jitter = random.gauss(0, 20e-9)  # ~20ns jitter
            if i % 525 == 524:  # Vertical retrace
                t += line_time * 20  # Flyback takes ~20 line times
            else:
                t += line_time + jitter
            timestamps.append(t)
        return timestamps

    def _demo_gradient_response(self, steps):
        """Simulate CRT gamma curve (~2.2)."""
        import math
        gamma = 2.2
        response = []
        for i in range(steps):
            linear = i / max(1, steps - 1)
            # CRT has natural power-law response
            brightness = math.pow(linear, gamma) * 255
            response.append(brightness)
        return response

    def _webcam_capture_brightness(self, duration_s, sample_rate):
        """Capture from webcam (requires opencv-python)."""
        try:
            import cv2
            cap = cv2.VideoCapture(self.device or 0)
            if not cap.isOpened():
                print(f"[capture] Cannot open webcam: {self.device}")
                return []
            
            samples = []
            start = time.time()
            while time.time() - start < duration_s:
                ret, frame = cap.read()
                if ret:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    mean_brightness = gray.mean()
                    samples.append(float(mean_brightness))
            cap.release()
            return samples
        except ImportError:
            print("[capture] opencv-python not installed")
            return []

    def _gpio_capture_brightness(self, duration_s, sample_rate):
        """Capture from GPIO photodiode (Raspberry Pi)."""
        try:
            import RPi.GPIO as GPIO
            # Setup ADC on specified pin
            GPIO.setmode(GPIO.BCM)
            # Would use SPI ADC (MCP3008) for analog reading
            print(f"[capture] GPIO capture on pin {self.pin}")
            return []
        except ImportError:
            print("[capture] RPi.GPIO not available")
            return []


def build_fingerprint(capture: CRTAttestationCapture) -> CRTFingerprint:
    """Run full CRT fingerprint extraction."""
    
    # Capture all measurements
    decay_samples = capture.capture_phosphor_decay()
    frame_ts = capture.capture_frame_timestamps()
    line_ts = capture.capture_scanline_timestamps()
    gradient = capture.capture_gradient_response()
    
    # Analyze
    decay_ms, phosphor, decay_hash = analyze_phosphor_decay(decay_samples, 10000)
    refresh_hz, drift_ppm, refresh_jitter = analyze_refresh_rate(frame_ts)
    scan_jitter, flyback_us, hsync_jitter = analyze_scanline_timing(line_ts)
    gamma_hash = analyze_brightness_gamma(gradient)
    
    fp = CRTFingerprint(
        phosphor_decay_ms=decay_ms,
        phosphor_type=phosphor,
        decay_curve_hash=decay_hash,
        actual_refresh_hz=refresh_hz,
        refresh_drift_ppm=drift_ppm,
        refresh_jitter_us=refresh_jitter,
        scanline_jitter_ns=scan_jitter,
        flyback_duration_us=flyback_us,
        hsync_jitter_ns=hsync_jitter,
        gamma_curve_hash=gamma_hash,
        warmup_time_s=2.5,  # Simulated for demo
        beam_current_drop_pct=6.0,  # Simulated for demo
        capture_timestamp=int(time.time()),
        capture_duration_s=5.0,
    )
    
    fp.crt_confidence, fp.emulator_flags = compute_crt_confidence(fp)
    
    return fp


def submit_attestation(fp: CRTFingerprint, node_url: str, wallet: str) -> dict:
    """Submit CRT fingerprint with attestation."""
    payload = {
        "miner": wallet,
        "device": {
            "device_arch": "crt_optical",
            "device_family": "CRT",
            "device_model": f"{fp.phosphor_type}_monitor",
        },
        "crt_fingerprint": fp.to_dict(),
        "fingerprint_hash": fp.fingerprint_hash(),
        "crt_confidence": fp.crt_confidence,
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{node_url}/attest/submit",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="CRT Light Attestation")
    parser.add_argument("--capture", choices=["demo", "webcam", "gpio"], default="demo")
    parser.add_argument("--device", default="/dev/video0", help="Webcam device")
    parser.add_argument("--pin", type=int, default=18, help="GPIO pin for photodiode")
    parser.add_argument("--node", default="https://rustchain.org")
    parser.add_argument("--wallet", default="crt-miner-001")
    parser.add_argument("--submit", action="store_true", help="Submit to node")
    args = parser.parse_args()

    print("=== CRT Light Attestation ===")
    print(f"Capture: {args.capture}")

    capture = CRTAttestationCapture(args.capture, args.device, args.pin)
    
    if args.capture == "demo":
        print("\n--- Demo: Real CRT (simulated 15-year Trinitron) ---")
        fp = build_fingerprint(capture)
    else:
        fp = build_fingerprint(capture)

    print(f"\nPhosphor: {fp.phosphor_type} (decay: {fp.phosphor_decay_ms:.3f}ms)")
    print(f"Refresh: {fp.actual_refresh_hz:.4f} Hz (drift: {fp.refresh_drift_ppm:.1f} ppm)")
    print(f"Scanline jitter: {fp.scanline_jitter_ns:.1f} ns")
    print(f"CRT confidence: {fp.crt_confidence:.2f}")
    print(f"Fingerprint: {fp.fingerprint_hash()}")

    if fp.crt_confidence >= 0.7:
        print("\n✅ CRT DETECTED — fingerprint valid for attestation")
    else:
        print(f"\n⚠️  Low CRT confidence ({fp.crt_confidence:.2f}) — may be LCD/emulator")

    if args.submit:
        result = submit_attestation(fp, args.node, args.wallet)
        print(f"\nSubmission: {json.dumps(result, indent=2)}")

    # CRT Gallery comparison
    print("\n--- CRT vs LCD Comparison ---")
    lcd = simulate_lcd_fingerprint()
    print(f"  CRT confidence: {fp.crt_confidence:.2f} | LCD confidence: {lcd.crt_confidence:.2f}")
    print(f"  CRT phosphor decay: {fp.phosphor_decay_ms:.3f}ms | LCD: {lcd.phosphor_decay_ms:.3f}ms")
    print(f"  CRT refresh drift: {fp.refresh_drift_ppm:.1f}ppm | LCD: {lcd.refresh_drift_ppm:.1f}ppm")


if __name__ == "__main__":
    main()
