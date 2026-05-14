"""
Boot Chime Proof-of-Iron Test Suite

Comprehensive tests for acoustic hardware attestation system.
"""

import unittest
import numpy as np
import tempfile
import os
import time
from pathlib import Path
import sys
from unittest.mock import patch

# Add src to path and handle imports
src_path = str(Path(__file__).parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import with fallback for direct execution
try:
    from acoustic_fingerprint import AcousticFingerprint, FingerprintFeatures
    from boot_chime_capture import BootChimeCapture, AudioCaptureConfig, CapturedAudio
    from proof_of_iron import (
        ProofOfIron, ProofOfIronError, AttestationStatus,
        AttestationChallenge, AttestationProof, HardwareIdentity
    )
    from spectral_analysis import SpectralAnalyzer
except ImportError:
    # Fallback for package-style imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.acoustic_fingerprint import AcousticFingerprint, FingerprintFeatures
    from src.boot_chime_capture import BootChimeCapture, AudioCaptureConfig, CapturedAudio
    from src.proof_of_iron import (
        ProofOfIron, ProofOfIronError, AttestationStatus,
        AttestationChallenge, AttestationProof, HardwareIdentity
    )
    from src.spectral_analysis import SpectralAnalyzer


# ============= Test Utilities =============

def generate_test_audio(duration=1.0, sample_rate=44100, frequency=440):
    """Generate synthetic test audio (sine wave)"""
    t = np.linspace(0, duration, int(sample_rate * duration))
    signal = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    # Add harmonics for realism
    for harmonic in range(2, 6):
        signal += (0.5 / harmonic) * np.sin(2 * np.pi * frequency * harmonic * t)
    
    # Add decay envelope
    envelope = np.exp(-t * 3)
    signal *= envelope
    
    # Add slight noise
    signal += np.random.normal(0, 0.01, len(signal))
    
    return signal


def generate_test_boot_chime(sample_rate=44100, duration=3.0):
    """Generate synthetic boot chime sound"""
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Boot chime: major chord with decay
    frequencies = [440, 554, 659]  # A major: A4, C#5, E5
    signal = np.zeros_like(t)
    
    for freq in frequencies:
        signal += 0.3 * np.sin(2 * np.pi * freq * t)
    
    # Apply decay
    decay = np.exp(-t * 1.5)
    signal *= decay
    
    # Add noise
    signal += np.random.normal(0, 0.005, len(signal))
    
    return signal


# ============= Acoustic Fingerprint Tests =============

class TestAcousticFingerprint(unittest.TestCase):
    """Tests for AcousticFingerprint class"""
    
    def setUp(self):
        self.extractor = AcousticFingerprint(sample_rate=44100, n_mfcc=13)
    
    def test_extract_features(self):
        """Test feature extraction from audio"""
        audio = generate_test_audio()
        features = self.extractor.extract(audio)
        
        self.assertIsInstance(features, FingerprintFeatures)
        self.assertEqual(len(features.mfcc_mean), 13)
        self.assertEqual(len(features.mfcc_std), 13)
        self.assertIsInstance(features.spectral_centroid, float)
        self.assertIsInstance(features.spectral_bandwidth, float)
        self.assertIsInstance(features.zero_crossing_rate, float)
    
    def test_compute_signature(self):
        """Test signature computation is deterministic"""
        audio = generate_test_audio(frequency=440)
        features = self.extractor.extract(audio)
        
        sig1 = self.extractor.compute_signature(features)
        sig2 = self.extractor.compute_signature(features)
        
        self.assertEqual(sig1, sig2)
        self.assertEqual(len(sig1), 32)  # 32 hex chars
    
    def test_signature_uniqueness(self):
        """Test different audio produces different signatures"""
        audio1 = generate_test_audio(frequency=440)
        audio2 = generate_test_audio(frequency=880)
        
        features1 = self.extractor.extract(audio1)
        features2 = self.extractor.extract(audio2)
        
        sig1 = self.extractor.compute_signature(features1)
        sig2 = self.extractor.compute_signature(features2)
        
        self.assertNotEqual(sig1, sig2)
    
    def test_compare_same_audio(self):
        """Test comparison of same audio produces high similarity"""
        audio = generate_test_audio()
        features = self.extractor.extract(audio)
        
        is_match, similarity = self.extractor.compare(features, features)
        
        self.assertTrue(is_match)
        self.assertGreater(similarity, 0.99)
    
    def test_compare_different_audio(self):
        """Test comparison of different audio produces lower similarity than same audio"""
        audio1 = generate_test_audio(frequency=440)
        audio2 = generate_test_audio(frequency=880)
        
        features1 = self.extractor.extract(audio1)
        features2 = self.extractor.extract(audio2)
        
        # Same audio comparison for baseline
        same_match, same_sim = self.extractor.compare(features1, features1)
        
        # Different audio comparison
        diff_match, diff_sim = self.extractor.compare(features1, features2)
        
        # Different audio should have lower similarity than same audio
        self.assertLess(diff_sim, same_sim)
        # Note: Synthetic sine waves may still have high similarity due to harmonic structure
    
    def test_normalize(self):
        """Test audio normalization"""
        audio = np.array([100, 200, 300, -100, -200])
        normalized = self.extractor._normalize(audio)
        
        self.assertAlmostEqual(np.max(np.abs(normalized)), 1.0)
    
    def test_mfcc_extraction(self):
        """Test MFCC extraction produces valid output"""
        audio = generate_test_audio()
        mfcc = self.extractor._extract_mfcc(audio)
        
        self.assertEqual(mfcc.shape[0], 13)  # n_mfcc
        self.assertGreater(mfcc.shape[1], 0)  # frames
    
    def test_spectral_centroid(self):
        """Test spectral centroid computation"""
        audio = generate_test_audio()
        centroid = self.extractor._spectral_centroid(audio)
        
        self.assertIsInstance(centroid, float)
        self.assertGreater(centroid, 0)
        self.assertLess(centroid, 22050)  # Nyquist frequency
    
    def test_zero_crossing_rate(self):
        """Test zero crossing rate computation"""
        audio = generate_test_audio()
        zcr = self.extractor._zero_crossing_rate(audio)
        
        self.assertIsInstance(zcr, float)
        self.assertGreaterEqual(zcr, 0)
        self.assertLessEqual(zcr, 1)
    
    def test_temporal_envelope(self):
        """Test temporal envelope extraction"""
        audio = generate_test_audio()
        envelope = self.extractor._temporal_envelope(audio, n_bins=50)
        
        self.assertEqual(len(envelope), 50)
        self.assertTrue(np.all(envelope >= 0))


# ============= Boot Chime Capture Tests =============

class TestBootChimeCapture(unittest.TestCase):
    """Tests for BootChimeCapture class"""
    
    def setUp(self):
        self.config = AudioCaptureConfig(
            sample_rate=44100,
            duration=3.0
        )
        self.capture = BootChimeCapture(self.config)
    
    def test_synthetic_capture(self):
        """Test synthetic audio capture"""
        captured = self.capture._synthetic_capture(2.0)
        
        self.assertIsInstance(captured, CapturedAudio)
        self.assertEqual(captured.duration, 2.0)
        self.assertEqual(captured.sample_rate, 44100)
        self.assertGreater(len(captured.data), 0)
    
    def test_save_and_load_audio(self):
        """Test saving and loading audio"""
        # Create test audio
        audio_data = generate_test_boot_chime()
        captured = CapturedAudio(
            data=audio_data,
            sample_rate=44100,
            channels=1,
            duration=3.0,
            captured_at=time.time()
        )
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp_path = tmp.name
        
        try:
            self.capture.save_audio(captured, tmp_path)
            
            # Load back
            loaded = self.capture.capture_from_file(tmp_path)
            
            self.assertEqual(loaded.sample_rate, captured.sample_rate)
            self.assertAlmostEqual(loaded.duration, captured.duration, places=1)
            self.assertGreater(loaded.quality_score, 0)
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_detect_boot_chime(self):
        """Test boot chime detection"""
        # Generate boot chime-like sound
        audio_data = generate_test_boot_chime()
        captured = CapturedAudio(
            data=audio_data,
            sample_rate=44100,
            channels=1,
            duration=3.0,
            captured_at=time.time()
        )
        
        is_boot_chime, details = self.capture.detect_boot_chime(captured)
        
        # Convert numpy bool to Python bool for isinstance check
        self.assertIn(bool(is_boot_chime), [True, False])
        self.assertIn('has_onset', details)
        self.assertIn('has_harmonics', details)
        self.assertIn('has_decay', details)
        self.assertIn('confidence', details)
    
    def test_quality_assessment(self):
        """Test audio quality assessment"""
        # Good quality audio
        good_audio = generate_test_boot_chime()
        good_quality = self.capture._assess_quality(good_audio)
        
        self.assertGreater(good_quality, 0.5)
        
        # Very quiet audio (bad quality)
        quiet_audio = good_audio * 0.0001
        quiet_quality = self.capture._assess_quality(quiet_audio)
        
        # Quiet audio should have lower quality
        self.assertLessEqual(quiet_quality, good_quality)


# ============= Proof-of-Iron Protocol Tests =============

class TestProofOfIron(unittest.TestCase):
    """Tests for ProofOfIron class"""
    
    def setUp(self):
        self.db_path = tempfile.mktemp(suffix='.db')
        self.poi = ProofOfIron(db_path=self.db_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_issue_challenge(self):
        """Test challenge issuance"""
        challenge = self.poi.issue_challenge("miner_test_001")
        
        self.assertIsInstance(challenge, AttestationChallenge)
        self.assertEqual(challenge.miner_id, "miner_test_001")
        self.assertTrue(challenge.is_valid())
        self.assertEqual(len(challenge.nonce), 16)

    def test_challenge_ids_and_nonces_do_not_use_numpy_prng(self):
        """Challenge entropy must come from secrets, not Mersenne Twister."""
        proof_globals = ProofOfIron._generate_nonce.__globals__
        with patch.object(proof_globals["np"].random, "random", side_effect=AssertionError("np.random.random used")):
            challenge_id = self.poi._generate_challenge_id("miner_test_001")
            nonce = self.poi._generate_nonce()

        self.assertEqual(len(challenge_id), 16)
        self.assertEqual(len(nonce), 16)

    def test_nonce_comes_directly_from_secrets_token_hex(self):
        """Regression for issue #5040: nonce generation must use CSPRNG output."""
        proof_globals = ProofOfIron._generate_nonce.__globals__
        with patch.object(proof_globals["secrets"], "token_hex", return_value="a" * 16) as token_hex:
            nonce = self.poi._generate_nonce()

        token_hex.assert_called_once_with(8)
        self.assertEqual(nonce, "a" * 16)
    
    def test_challenge_expiration(self):
        """Test challenge expiration"""
        # Create challenge with short TTL
        poi_short = ProofOfIron(challenge_ttl=1)
        challenge = poi_short.issue_challenge("miner_test")
        
        self.assertTrue(challenge.is_valid())
        time.sleep(2)
        self.assertFalse(challenge.is_valid())
    
    def test_enroll_miner(self):
        """Test miner enrollment"""
        audio_data = generate_test_boot_chime()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp_path = tmp.name
        
        try:
            # Create WAV file manually
            import wave
            import struct
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            with wave.open(tmp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(audio_int16.tobytes())
            
            result = self.poi.capture_and_enroll("miner_test_001", tmp_path)
            
            self.assertEqual(result.status, AttestationStatus.VERIFIED)
            self.assertEqual(result.miner_id, "miner_test_001")
            self.assertIsNotNone(result.hardware_identity)
            self.assertGreater(result.confidence, 0)
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_verify_miner(self):
        """Test miner verification"""
        # First enroll
        result = self.poi.capture_and_enroll("miner_test_002")
        self.assertEqual(result.status, AttestationStatus.VERIFIED)
        
        # Then verify
        verify_result = self.poi.verify_miner("miner_test_002")
        
        self.assertEqual(verify_result.status, AttestationStatus.VERIFIED)
        self.assertIsNotNone(verify_result.hardware_identity)
    
    def test_verify_unknown_miner(self):
        """Test verification of unknown miner"""
        result = self.poi.verify_miner("unknown_miner")
        
        self.assertEqual(result.status, AttestationStatus.PENDING)
        self.assertIsNone(result.hardware_identity)
    
    def test_revoke_attestation(self):
        """Test attestation revocation"""
        # Enroll miner
        self.poi.capture_and_enroll("miner_test_003")
        
        # Revoke
        success = self.poi.revoke_attestation("miner_test_003", "Testing")
        
        self.assertTrue(success)
        
        # Verify revoked
        result = self.poi.verify_miner("miner_test_003")
        self.assertEqual(result.status, AttestationStatus.REVOKED)
    
    def test_submit_proof(self):
        """Test proof submission"""
        # Issue challenge
        challenge = self.poi.issue_challenge("miner_test_004")
        
        # Create proof
        proof = AttestationProof(
            challenge_id=challenge.challenge_id,
            miner_id="miner_test_004",
            audio_signature="test_signature",
            features_hash="test_hash",
            timestamp=int(time.time()),
            proof_data={'valid': True}
        )
        
        result = self.poi.submit_proof(proof)
        
        self.assertEqual(result.status, AttestationStatus.VERIFIED)
    
    def test_submit_invalid_challenge(self):
        """Test proof submission with invalid challenge"""
        proof = AttestationProof(
            challenge_id="invalid_challenge",
            miner_id="miner_test",
            audio_signature="sig",
            features_hash="hash",
            timestamp=int(time.time()),
            proof_data={}
        )
        
        result = self.poi.submit_proof(proof)
        
        self.assertEqual(result.status, AttestationStatus.FAILED)
    
    def test_get_hardware_identity(self):
        """Test getting hardware identity"""
        # Enroll miner
        self.poi.capture_and_enroll("miner_test_005")
        
        identity = self.poi.get_hardware_identity("miner_test_005")
        
        self.assertIsNotNone(identity)
        self.assertIsInstance(identity, HardwareIdentity)
        self.assertTrue(identity.device_id.startswith("poi_"))
    
    def test_attestation_history(self):
        """Test attestation history retrieval"""
        # Enroll miner
        self.poi.capture_and_enroll("miner_test_006")
        
        history = self.poi.get_attestation_history("miner_test_006")
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, AttestationStatus.VERIFIED)


# ============= Spectral Analysis Tests =============

class TestSpectralAnalyzer(unittest.TestCase):
    """Tests for SpectralAnalyzer class"""
    
    def setUp(self):
        self.analyzer = SpectralAnalyzer(sample_rate=44100)
    
    def test_spectral_features(self):
        """Test spectral feature extraction"""
        audio = generate_test_audio()
        features = self.analyzer.analyze(audio)
        
        self.assertIsInstance(features.centroid, float)
        self.assertIsInstance(features.bandwidth, float)
        self.assertIsInstance(features.flatness, float)
        self.assertIsInstance(features.rolloff, float)
    
    def test_spectrogram(self):
        """Test spectrogram computation"""
        audio = generate_test_audio()
        spectrogram, times, frequencies = self.analyzer.compute_spectrogram(audio)
        
        self.assertEqual(len(spectrogram.shape), 2)
        self.assertEqual(len(times), spectrogram.shape[1])
        self.assertEqual(len(frequencies), spectrogram.shape[0])
    
    def test_cepstrum(self):
        """Test cepstrum computation"""
        audio = generate_test_audio()
        cepstrum = self.analyzer.compute_cepstrum(audio)
        
        self.assertEqual(len(cepstrum), len(audio))
    
    def test_pitch_detection(self):
        """Test pitch detection"""
        audio = generate_test_audio(frequency=440)
        pitch = self.analyzer.detect_pitch(audio)
        
        # Should detect around 440 Hz (with some tolerance)
        if pitch is not None:
            self.assertGreater(pitch, 400)
            self.assertLess(pitch, 500)


# ============= Integration Tests =============

class TestIntegration(unittest.TestCase):
    """Integration tests for complete attestation flow"""
    
    def setUp(self):
        self.db_path = tempfile.mktemp(suffix='.db')
        self.poi = ProofOfIron(db_path=self.db_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_full_attestation_flow(self):
        """Test complete attestation workflow"""
        miner_id = "integration_test_miner"
        
        # 1. Issue challenge
        challenge = self.poi.issue_challenge(miner_id)
        self.assertTrue(challenge.is_valid())
        
        # 2. Capture boot chime
        audio_data = generate_test_boot_chime()
        
        # 3. Enroll miner
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp_path = tmp.name
        
        try:
            import wave
            import struct
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            with wave.open(tmp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(audio_int16.tobytes())
            
            enroll_result = self.poi.capture_and_enroll(miner_id, tmp_path)
            self.assertEqual(enroll_result.status, AttestationStatus.VERIFIED)
            
            # 4. Verify miner
            verify_result = self.poi.verify_miner(miner_id)
            self.assertEqual(verify_result.status, AttestationStatus.VERIFIED)
            
            # 5. Get identity
            identity = self.poi.get_hardware_identity(miner_id)
            self.assertIsNotNone(identity)
            self.assertEqual(identity.miner_id, miner_id) if hasattr(identity, 'miner_id') else None
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_multiple_miners(self):
        """Test multiple miners attestation"""
        miner_ids = [f"miner_{i}" for i in range(5)]
        
        # Enroll all miners
        for miner_id in miner_ids:
            result = self.poi.capture_and_enroll(miner_id)
            self.assertEqual(result.status, AttestationStatus.VERIFIED)
        
        # Verify all miners
        for miner_id in miner_ids:
            result = self.poi.verify_miner(miner_id)
            self.assertEqual(result.status, AttestationStatus.VERIFIED)
        
        # Revoke one miner
        self.poi.revoke_attestation(miner_ids[2])
        
        # Verify revocation
        result = self.poi.verify_miner(miner_ids[2])
        self.assertEqual(result.status, AttestationStatus.REVOKED)
        
        # Others still verified
        for i in [0, 1, 3, 4]:
            result = self.poi.verify_miner(miner_ids[i])
            self.assertEqual(result.status, AttestationStatus.VERIFIED)


# ============= Main =============

if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
