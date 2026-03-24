# SPDX-License-Identifier: MIT
"""Unit tests for Boot Chime Proof-of-Iron (Bounty #2307)."""

import math
import pytest
from boot_chime import (
    SpectralFingerprint,
    ChimeMatchResult,
    KNOWN_PROFILES,
    extract_spectral_fingerprint,
    match_profile,
    validate_acoustic_attestation,
    simple_fft_peaks,
)


# ── Helpers ───────────────────────────────────────────────────────

def generate_sine(freq_hz: float, duration_s: float = 0.5,
                  sample_rate: int = 44100, amplitude: float = 0.5,
                  noise: float = 0.0) -> list:
    """Generate a sine wave with optional noise (simulates real hardware)."""
    import random
    n = int(sample_rate * duration_s)
    samples = []
    for i in range(n):
        t = i / sample_rate
        val = amplitude * math.sin(2 * math.pi * freq_hz * t)
        if noise > 0:
            val += random.gauss(0, noise)
        samples.append(val)
    return samples


def generate_chime(profile_id: str, analog_noise: float = 0.01) -> list:
    """Generate a synthetic boot chime matching a known profile."""
    profile = KNOWN_PROFILES[profile_id]
    duration_s = profile["duration_ms"] / 1000.0
    sample_rate = 44100
    n = int(sample_rate * duration_s)

    samples = []
    for i in range(n):
        t = i / sample_rate
        # Fundamental
        val = 0.5 * math.sin(2 * math.pi * profile["fundamental_hz"] * t)
        # Harmonics with decreasing amplitude
        for j, harm_hz in enumerate(profile["harmonics"]):
            val += (0.2 / (j + 1)) * math.sin(2 * math.pi * harm_hz * t)
        # Decay envelope
        decay = math.exp(-t * (1.0 - profile["decay_rate"]) * 5)
        val *= decay
        # Analog noise (real hardware has this)
        if analog_noise > 0:
            import random
            val += random.gauss(0, analog_noise)
        samples.append(val)

    return samples


# ── SpectralFingerprint Tests ─────────────────────────────────────

class TestSpectralFingerprint:
    def test_compute_hash(self):
        fp = SpectralFingerprint(fundamental_hz=523.25, spectral_centroid_hz=800)
        h = fp.compute_hash()
        assert len(h) == 32
        assert fp.fingerprint_hash == h

    def test_hash_deterministic(self):
        fp1 = SpectralFingerprint(fundamental_hz=523.25, noise_floor_db=-48)
        fp2 = SpectralFingerprint(fundamental_hz=523.25, noise_floor_db=-48)
        assert fp1.compute_hash() == fp2.compute_hash()

    def test_hash_changes_with_data(self):
        fp1 = SpectralFingerprint(fundamental_hz=523.25)
        fp2 = SpectralFingerprint(fundamental_hz=440.0)
        assert fp1.compute_hash() != fp2.compute_hash()

    def test_to_dict(self):
        fp = SpectralFingerprint(fundamental_hz=440.0, duration_ms=200)
        d = fp.to_dict()
        assert d["fundamental_hz"] == 440.0
        assert d["duration_ms"] == 200


# ── FFT Peak Detection Tests ─────────────────────────────────────

class TestFFTPeaks:
    def test_detect_single_frequency(self):
        samples = generate_sine(440.0, duration_s=0.1, sample_rate=44100)
        peaks = simple_fft_peaks(samples, sample_rate=44100, n_peaks=3)
        assert len(peaks) >= 1
        # Fundamental should be near 440 Hz (within FFT resolution)
        assert abs(peaks[0][0] - 440.0) < 50  # ~10 Hz resolution at 0.1s

    def test_empty_samples(self):
        peaks = simple_fft_peaks([], 44100)
        assert peaks == []


# ── Extraction Tests ──────────────────────────────────────────────

class TestExtraction:
    def test_extract_from_sine(self):
        samples = generate_sine(523.25, duration_s=0.1, noise=0.01)
        fp = extract_spectral_fingerprint(samples, sample_rate=44100)
        assert fp.rms_energy > 0
        assert fp.duration_ms > 0
        assert fp.collected_at != ""
        assert fp.fingerprint_hash != ""

    def test_extract_noise_floor(self):
        samples = generate_sine(440.0, duration_s=0.1, noise=0.02)
        fp = extract_spectral_fingerprint(samples, sample_rate=44100)
        # Noise floor should be in analog range (not digital silence)
        assert fp.noise_floor_db < 0

    def test_extract_empty(self):
        fp = extract_spectral_fingerprint([])
        assert fp.rms_energy == 0

    def test_extract_zero_crossing(self):
        samples = generate_sine(440.0, duration_s=0.1)
        fp = extract_spectral_fingerprint(samples, sample_rate=44100)
        assert fp.zero_crossing_rate > 0


# ── Profile Matching Tests ────────────────────────────────────────

class TestProfileMatching:
    def test_match_mac_g4_profile(self):
        """Synthetic G4 chime should match G4 profile."""
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            spectral_centroid_hz=820,
            duration_ms=1100,
            decay_rate=0.88,
            noise_floor_db=-48,
        )
        result = match_profile(fp)
        assert result.matched is True
        assert "mac" in result.profile_name.lower() or "g4" in result.profile_id

    def test_match_amiga_profile(self):
        fp = SpectralFingerprint(
            fundamental_hz=440.0,
            spectral_centroid_hz=600,
            duration_ms=200,
            decay_rate=0.70,
            noise_floor_db=-38,
        )
        result = match_profile(fp)
        assert result.matched is True
        assert "amiga" in result.profile_id

    def test_no_match_garbage(self):
        """Random data should not match any profile."""
        fp = SpectralFingerprint(
            fundamental_hz=12345.0,
            spectral_centroid_hz=9999,
            duration_ms=50,
            decay_rate=0.01,
        )
        result = match_profile(fp)
        assert result.matched is False

    def test_emulator_detection(self):
        """Emulator has too-clean noise floor."""
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            spectral_centroid_hz=820,
            duration_ms=1100,
            decay_rate=0.88,
            noise_floor_db=-95,  # Digital silence = emulator
        )
        result = match_profile(fp)
        assert result.is_emulator is True
        assert result.analog_artifacts_detected is False

    def test_real_hardware_analog_artifacts(self):
        """Real hardware has noise floor between -60 and -20 dB."""
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            noise_floor_db=-45,
        )
        result = match_profile(fp)
        assert result.analog_artifacts_detected is True
        assert result.is_emulator is False


# ── Validation Pipeline Tests ─────────────────────────────────────

class TestValidation:
    def test_valid_g4_chime_accepted(self):
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            spectral_centroid_hz=820,
            duration_ms=1100,
            decay_rate=0.88,
            noise_floor_db=-48,
        )
        fp.compute_hash()
        ok, reason, bonus = validate_acoustic_attestation(fp, "G4")
        assert ok is True
        assert "ACCEPTED" in reason
        assert bonus > 0

    def test_emulator_rejected(self):
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            spectral_centroid_hz=820,
            duration_ms=1100,
            decay_rate=0.88,
            noise_floor_db=-95,
        )
        fp.compute_hash()
        ok, reason, bonus = validate_acoustic_attestation(fp)
        assert ok is False
        assert "EMULATOR" in reason

    def test_no_match_rejected(self):
        fp = SpectralFingerprint(
            fundamental_hz=9999.0,
            noise_floor_db=-40,
        )
        fp.compute_hash()
        ok, reason, bonus = validate_acoustic_attestation(fp)
        assert ok is False
        assert "NO_MATCH" in reason

    def test_empty_fingerprint_rejected(self):
        fp = SpectralFingerprint()
        ok, reason, bonus = validate_acoustic_attestation(fp)
        assert ok is False
        assert "NO_FINGERPRINT" in reason

    def test_arch_mismatch_rejected(self):
        """Claiming G4 but chime matches Amiga → rejected."""
        fp = SpectralFingerprint(
            fundamental_hz=440.0,
            spectral_centroid_hz=600,
            duration_ms=200,
            decay_rate=0.70,
            noise_floor_db=-38,
        )
        fp.compute_hash()
        ok, reason, bonus = validate_acoustic_attestation(fp, "G4")
        assert ok is False
        assert "MISMATCH" in reason

    def test_high_confidence_bonus(self):
        """High confidence match gets extra bonus."""
        fp = SpectralFingerprint(
            fundamental_hz=523.25,
            spectral_centroid_hz=820,
            duration_ms=1100,
            decay_rate=0.88,
            noise_floor_db=-48,
        )
        fp.compute_hash()
        ok, reason, bonus = validate_acoustic_attestation(fp)
        assert bonus >= 0.10  # base + analog + confidence


# ── Known Profiles Tests ──────────────────────────────────────────

class TestKnownProfiles:
    def test_all_profiles_have_required_fields(self):
        required = ["name", "fundamental_hz", "harmonics", "duration_ms",
                     "decay_rate", "spectral_centroid_hz", "hiss_floor_db"]
        for pid, profile in KNOWN_PROFILES.items():
            for field in required:
                assert field in profile, f"{pid} missing {field}"

    def test_profile_count(self):
        assert len(KNOWN_PROFILES) >= 6

    def test_mac_profiles_use_c5(self):
        """All Mac boot chimes use C5 (523.25 Hz)."""
        for pid, p in KNOWN_PROFILES.items():
            if "mac" in pid:
                assert p["fundamental_hz"] == 523.25
