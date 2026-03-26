"""
Comprehensive Test Suite for CRT Light Attestation

Tests all components:
- Pattern generation
- Capture module
- Analyzer
- Attestation submission
- CLI interface
"""

import pytest
import numpy as np
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from crt_pattern_generator import CRTPatternGenerator, generate_test_patterns
from crt_capture import CRTCapture, CaptureConfig, CaptureMethod, CapturedFrame
from crt_analyzer import CRTAnalyzer, CRTFingerprint
from crt_attestation_submitter import (
    CRTAttestationSubmitter, 
    CRTAttestation,
    CRTAttestationIntegration,
    create_sample_attestation
)


# ============================================================================
# Pattern Generator Tests
# ============================================================================

class TestPatternGenerator:
    """Tests for CRTPatternGenerator"""
    
    def test_initialization(self):
        """Test generator initialization with default parameters"""
        gen = CRTPatternGenerator()
        assert gen.width == 1920
        assert gen.height == 1080
        assert gen.refresh_rate == 60.0
        assert gen.phosphor_type == 'P22'
    
    def test_custom_initialization(self):
        """Test generator with custom parameters"""
        gen = CRTPatternGenerator(
            width=1024,
            height=768,
            refresh_rate=72.0,
            phosphor_type='P43'
        )
        assert gen.width == 1024
        assert gen.phosphor_decay == 0.200  # P43 decay time
    
    def test_checkered_pattern_shape(self):
        """Test checkered pattern has correct shape"""
        gen = CRTPatternGenerator(width=640, height=480)
        pattern = gen.generate_checkered_pattern()
        assert pattern.shape == (480, 640, 3)
        assert pattern.dtype == np.uint8
    
    def test_checkered_pattern_determinism(self):
        """Test checkered pattern is deterministic"""
        gen = CRTPatternGenerator(width=100, height=100)
        pattern1 = gen.generate_checkered_pattern()
        pattern2 = gen.generate_checkered_pattern()
        assert np.array_equal(pattern1, pattern2)
    
    def test_gradient_sweep(self):
        """Test gradient sweep generation"""
        gen = CRTPatternGenerator(width=256, height=100)
        
        # Horizontal gradient
        h_grad = gen.generate_gradient_sweep('horizontal')
        assert h_grad.shape == (100, 256, 3)
        
        # Verify gradient increases left to right
        for row in range(0, 100, 10):
            assert h_grad[row, 0, 0] <= h_grad[row, -1, 0]
        
        # Vertical gradient
        v_grad = gen.generate_gradient_sweep('vertical')
        assert v_grad.shape == (100, 256, 3)
    
    def test_timing_bars(self):
        """Test timing bars generation"""
        gen = CRTPatternGenerator(width=640, height=480)
        bars = gen.generate_timing_bars(num_bars=10)
        assert bars.shape == (480, 640, 3)
        
        # Should have some red and green pixels
        red_pixels = np.sum((bars[:, :, 0] > 200) & (bars[:, :, 1] < 50))
        green_pixels = np.sum((bars[:, :, 1] > 200) & (bars[:, :, 0] < 50))
        assert red_pixels > 0
        assert green_pixels > 0
    
    def test_phosphor_patterns(self):
        """Test phosphor test patterns"""
        gen = CRTPatternGenerator()
        
        flash = gen.generate_phosphor_test_pattern('flash')
        assert np.all(flash == 255)  # Full white
        
        pulse = gen.generate_phosphor_test_pattern('pulse')
        assert pulse.shape == (1080, 1920, 3)
        
        zone = gen.generate_phosphor_test_pattern('zone')
        assert zone.shape == (1080, 1920, 3)
    
    def test_composite_pattern(self):
        """Test composite pattern generation"""
        gen = CRTPatternGenerator()
        composite = gen.generate_composite_pattern()
        assert composite.shape == (1080, 1920, 3)
        
        # Should have edge markers
        assert np.all(composite[0:10, :, 0] == 255)  # Top white
    
    def test_pattern_hash_determinism(self):
        """Test pattern hash is deterministic"""
        gen = CRTPatternGenerator()
        pattern1 = gen.generate_checkered_pattern()
        pattern2 = gen.generate_checkered_pattern()
        
        hash1 = gen.compute_pattern_hash(pattern1)
        hash2 = gen.compute_pattern_hash(pattern2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_pattern_hash_uniqueness(self):
        """Test different patterns have different hashes"""
        gen = CRTPatternGenerator()
        
        checkered = gen.generate_checkered_pattern()
        gradient = gen.generate_gradient_sweep()
        
        hash1 = gen.compute_pattern_hash(checkered)
        hash2 = gen.compute_pattern_hash(gradient)
        
        assert hash1 != hash2
    
    def test_fingerprint_seed(self):
        """Test fingerprint seed generation"""
        gen = CRTPatternGenerator()
        seed1 = gen.generate_fingerprint_seed()
        seed2 = gen.generate_fingerprint_seed()
        
        # Same minute should produce same seed
        assert len(seed1) == 16
    
    def test_metadata(self):
        """Test pattern metadata generation"""
        gen = CRTPatternGenerator(
            width=1024,
            height=768,
            refresh_rate=85.0,
            phosphor_type='P43'
        )
        meta = gen.get_pattern_metadata()
        
        assert meta['width'] == 1024
        assert meta['height'] == 768
        assert meta['refresh_rate'] == 85.0
        assert meta['phosphor_type'] == 'P43'
        assert 'fingerprint_seed' in meta
    
    def test_generate_test_patterns(self):
        """Test generate_test_patterns utility function"""
        result = generate_test_patterns()
        
        assert 'patterns' in result
        assert 'metadata' in result
        assert 'hashes' in result
        
        expected_patterns = [
            'checkered', 'gradient_h', 'gradient_v',
            'timing_bars', 'phosphor_flash', 'phosphor_pulse',
            'phosphor_zone', 'composite'
        ]
        for name in expected_patterns:
            assert name in result['patterns']


# ============================================================================
# Capture Module Tests
# ============================================================================

class TestCapture:
    """Tests for CRTCapture module"""
    
    def test_capture_config_defaults(self):
        """Test capture configuration defaults"""
        config = CaptureConfig()
        assert config.method == CaptureMethod.SIMULATED
        assert config.fps == 30
        assert config.capture_duration_s == 5.0
    
    def test_capture_initialization(self):
        """Test capture module initialization"""
        config = CaptureConfig(method=CaptureMethod.SIMULATED)
        capture = CRTCapture(config)
        assert capture.is_capturing == False
        assert len(capture.captured_frames) == 0
    
    def test_dark_frame_calibration(self):
        """Test dark frame calibration"""
        config = CaptureConfig(width=320, height=240)
        capture = CRTCapture(config)
        
        dark = capture.calibrate_dark_frame()
        assert dark.shape == (240, 320, 3)
        assert capture.dark_frame is not None
    
    def test_flat_field_calibration(self):
        """Test flat field calibration"""
        config = CaptureConfig(width=320, height=240)
        capture = CRTCapture(config)
        
        flat = capture.calibrate_flat_field()
        assert flat.shape == (240, 320, 3)
        assert capture.flat_field is not None
    
    def test_start_stop_capture(self):
        """Test capture start/stop"""
        capture = CRTCapture()
        
        assert capture.start_capture() == True
        assert capture.is_capturing == True
        
        capture.stop_capture()
        assert capture.is_capturing == False
    
    def test_capture_frame_simulated(self):
        """Test frame capture in simulated mode"""
        config = CaptureConfig(
            method=CaptureMethod.SIMULATED,
            width=160,
            height=120
        )
        capture = CRTCapture(config)
        capture.start_capture()
        
        frame = capture.capture_frame()
        assert frame is not None
        assert isinstance(frame, CapturedFrame)
        assert frame.data.shape == (120, 160, 3)
    
    def test_capture_sequence(self):
        """Test sequence capture"""
        config = CaptureConfig(
            method=CaptureMethod.SIMULATED,
            fps=10,
            capture_duration_s=1.0
        )
        capture = CRTCapture(config)
        
        frames = capture.capture_sequence()
        assert len(frames) >= 8  # At least 8 frames in 1 second at 10fps
    
    def test_captured_data_export(self):
        """Test captured data export"""
        config = CaptureConfig(method=CaptureMethod.SIMULATED)
        capture = CRTCapture(config)
        capture.start_capture()
        
        # Capture a few frames
        for _ in range(3):
            capture.capture_frame()
        
        data = capture.get_captured_data()
        
        assert 'config' in data
        assert 'num_frames' in data
        assert 'frames' in data
        assert data['num_frames'] == 3
    
    def test_capture_statistics(self):
        """Test capture statistics"""
        config = CaptureConfig(method=CaptureMethod.SIMULATED)
        capture = CRTCapture(config)
        
        # No frames yet
        stats = capture.get_capture_statistics()
        assert 'error' in stats
        
        # Capture frames
        capture.start_capture()
        for _ in range(5):
            capture.capture_frame()
        
        stats = capture.get_capture_statistics()
        assert stats['num_frames'] == 5
        assert 'mean_intensity' in stats
        assert 'actual_fps' in stats
    
    def test_scanline_extraction(self):
        """Test scanline extraction from frame"""
        config = CaptureConfig(width=320, height=240)
        capture = CRTCapture(config)
        
        # Create frame with horizontal lines
        frame = np.zeros((240, 320), dtype=np.uint8)
        frame[50:52, :] = 255  # Bright line
        frame[150:152, :] = 255  # Another bright line
        
        scanlines = capture.extract_scanlines(frame)
        assert len(scanlines) > 0
    
    def test_dark_subtraction(self):
        """Test dark frame subtraction"""
        config = CaptureConfig()
        capture = CRTCapture(config)
        capture.calibrate_dark_frame()
        
        # Create bright frame
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 100
        
        corrected = capture.apply_dark_subtraction(frame)
        assert corrected.shape == frame.shape
    
    def test_flat_field_correction(self):
        """Test flat field correction"""
        config = CaptureConfig()
        capture = CRTCapture(config)
        capture.calibrate_flat_field()
        
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        corrected = capture.apply_flat_field_correction(frame)
        assert corrected.shape == frame.shape


# ============================================================================
# Analyzer Tests
# ============================================================================

class TestAnalyzer:
    """Tests for CRTAnalyzer module"""
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        analyzer = CRTAnalyzer(expected_refresh_rate=60.0)
        assert analyzer.expected_refresh_rate == 60.0
        assert analyzer.sample_rate == 30.0
    
    def test_refresh_rate_analysis(self):
        """Test refresh rate analysis"""
        analyzer = CRTAnalyzer(expected_refresh_rate=60.0)
        
        # Simulate intensity data with 60Hz component
        np.random.seed(42)
        duration = 2.0
        sample_rate = 30
        t = np.linspace(0, duration, int(duration * sample_rate))
        intensities = 128 + 50 * np.sin(2 * np.pi * 60 * t)
        
        measured, drift = analyzer.analyze_refresh_rate(intensities, t)
        
        assert measured > 0
        assert isinstance(drift, float)
    
    def test_phosphor_decay_analysis(self):
        """Test phosphor decay analysis"""
        analyzer = CRTAnalyzer()
        
        # Simulate exponential decay
        t = np.linspace(0, 0.5, 100)
        tau = 0.033  # 33ms decay
        response = np.exp(-t / tau)
        
        decay_ms, phosphor_type = analyzer.analyze_phosphor_decay(response, t)
        
        assert decay_ms > 0
        assert phosphor_type in analyzer.PHOSPHOR_DECAY_CONSTANTS.keys()
    
    def test_scanline_jitter_analysis(self):
        """Test scanline jitter analysis"""
        analyzer = CRTAnalyzer()
        
        # Simulate scanline positions with jitter
        positions = [i * 10 + np.random.normal(0, 0.5) for i in range(100)]
        
        jitter = analyzer.analyze_scanline_jitter(positions, 100)
        
        assert jitter >= 0
    
    def test_brightness_nonlinearity_analysis(self):
        """Test brightness nonlinearity (gamma) analysis"""
        analyzer = CRTAnalyzer()
        
        # Simulate gamma curve (gamma = 2.2)
        expected = np.linspace(0, 1, 100)
        response = expected ** 2.2
        
        gamma = analyzer.analyze_brightness_nonlinearity(response, expected)
        
        assert gamma > 0
        assert 1.5 < gamma < 3.0  # Reasonable gamma range
    
    def test_electron_gun_wear_analysis(self):
        """Test electron gun wear estimation"""
        analyzer = CRTAnalyzer()
        
        # New CRT: high brightness, good uniformity
        wear_new = analyzer.analyze_electron_gun_wear(220, 0.95)
        
        # Old CRT: low brightness, poor uniformity
        wear_old = analyzer.analyze_electron_gun_wear(120, 0.7)
        
        assert 0 <= wear_new <= 1
        assert 0 <= wear_old <= 1
        assert wear_old > wear_new
    
    def test_flyback_drift_analysis(self):
        """Test flyback transformer drift analysis"""
        analyzer = CRTAnalyzer()
        
        drift = analyzer.analyze_flyback_drift(15734)
        
        assert isinstance(drift, float)
    
    def test_full_analysis(self):
        """Test complete fingerprint analysis"""
        analyzer = CRTAnalyzer()
        
        # Create simulated capture data
        np.random.seed(42)
        num_frames = 60
        timestamps = np.linspace(0, 2, num_frames)
        intensities = 128 + 50 * np.sin(2 * np.pi * 60 * timestamps)
        
        captured_data = {
            'frames': [
                {'timestamp': float(ts), 'mean_intensity': float(intensity)}
                for ts, intensity in zip(timestamps, intensities)
            ]
        }
        
        fingerprint = analyzer.analyze_full(captured_data)
        
        assert isinstance(fingerprint, CRTFingerprint)
        assert fingerprint.refresh_rate_measured > 0
        assert fingerprint.phosphor_decay_ms > 0
        assert len(fingerprint.unique_signature_hash) == 64
    
    def test_fingerprint_to_dict(self):
        """Test fingerprint dictionary conversion"""
        fp = CRTFingerprint(
            refresh_rate_measured=60.0,
            refresh_rate_drift_ppm=100,
            phosphor_decay_ms=0.033,
            phosphor_type_estimate='P22',
            scanline_jitter_us=0.5,
            brightness_nonlinearity_gamma=2.2,
            electron_gun_wear_estimate=0.2,
            flyback_transformer_drift_ppm=150,
            unique_signature_hash='test'
        )
        
        d = fp.to_dict()
        
        assert d['refresh_rate_measured'] == 60.0
        assert d['phosphor_type_estimate'] == 'P22'
    
    def test_analysis_report(self):
        """Test analysis report generation"""
        analyzer = CRTAnalyzer()
        
        # Perform analysis first
        analyzer.analysis_results = {
            'refresh_rate_drift_ppm': 200,
            'phosphor_decay_ms': 0.030,
            'electron_gun_wear_estimate': 0.25,
            'unique_signature_hash': 'test',
        }
        
        report = analyzer.get_analysis_report()
        
        assert 'summary' in report
        assert 'measurements' in report
        assert 'interpretation' in report
        assert report['summary']['crt_authenticated'] == True


# ============================================================================
# Attestation Submitter Tests
# ============================================================================

class TestAttestationSubmitter:
    """Tests for CRTAttestationSubmitter"""
    
    def test_submitter_initialization(self):
        """Test submitter initialization"""
        submitter = CRTAttestationSubmitter()
        assert submitter.node_url == "https://rustchain.org"
        assert submitter.last_attestation is None
    
    def test_create_attestation(self):
        """Test attestation creation"""
        submitter = CRTAttestationSubmitter()
        
        fingerprint = {
            'refresh_rate_measured': 60.0,
            'phosphor_decay_ms': 0.033,
            'scanline_jitter_us': 0.5,
            'brightness_nonlinearity_gamma': 2.2,
            'unique_signature_hash': 'test_hash',
        }
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash='pattern123',
            capture_method='simulated',
            confidence=0.95
        )
        
        assert attestation.version == "1.0.0"
        assert attestation.crt_fingerprint == fingerprint
        assert attestation.confidence_score == 0.95
        assert len(attestation.signature) == 64
    
    def test_attestation_to_dict(self):
        """Test attestation dictionary conversion"""
        attestation = CRTAttestation(
            version="1.0.0",
            timestamp=1234567890,
            crt_fingerprint={'test': 'data'},
            pattern_hash='hash123',
            capture_method='webcam',
            confidence_score=0.9,
            signature='sig'
        )
        
        d = attestation.to_dict()
        
        assert d['version'] == "1.0.0"
        assert d['crt_fingerprint'] == {'test': 'data'}
    
    def test_verify_attestation_valid(self):
        """Test verification of valid attestation"""
        submitter = CRTAttestationSubmitter()
        
        fingerprint = {
            'refresh_rate_measured': 60.0,
            'phosphor_decay_ms': 0.033,
            'scanline_jitter_us': 0.5,
            'brightness_nonlinearity_gamma': 2.2,
            'unique_signature_hash': 'test',
        }
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash='pattern',
            capture_method='simulated',
            confidence=0.95
        )
        
        is_valid = submitter.verify_attestation(attestation)
        assert is_valid == True
    
    def test_verify_attestation_expired(self):
        """Test verification rejects expired attestation"""
        submitter = CRTAttestationSubmitter()
        
        # Create attestation with old timestamp
        attestation = CRTAttestation(
            version="1.0.0",
            timestamp=0,  # Very old
            crt_fingerprint={'test': 'data'},
            pattern_hash='hash',
            capture_method='simulated',
            confidence_score=0.9,
            signature='sig'
        )
        
        is_valid = submitter.verify_attestation(attestation)
        assert is_valid == False
    
    def test_verify_attestation_missing_fields(self):
        """Test verification rejects missing fingerprint fields"""
        submitter = CRTAttestationSubmitter()
        
        attestation = CRTAttestation(
            version="1.0.0",
            timestamp=int(__import__('time').time()),
            crt_fingerprint={'incomplete': 'data'},  # Missing required fields
            pattern_hash='hash',
            capture_method='simulated',
            confidence_score=0.9,
            signature='sig'
        )
        
        is_valid = submitter.verify_attestation(attestation)
        assert is_valid == False
    
    def test_submit_attestation(self):
        """Test attestation submission"""
        submitter = CRTAttestationSubmitter()
        
        fingerprint = {
            'refresh_rate_measured': 60.0,
            'phosphor_decay_ms': 0.033,
            'scanline_jitter_us': 0.5,
            'brightness_nonlinearity_gamma': 2.2,
            'unique_signature_hash': 'test',
        }
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash='pattern',
            capture_method='simulated',
            confidence=0.95
        )
        
        result = submitter.submit_attestation(attestation)
        
        assert result['success'] == True
        assert 'submission_hash' in result
    
    def test_format_for_rustchain(self):
        """Test RustChain API formatting"""
        submitter = CRTAttestationSubmitter()
        
        fingerprint = {
            'refresh_rate_measured': 60.0,
            'phosphor_decay_ms': 0.033,
            'scanline_jitter_us': 0.5,
            'brightness_nonlinearity_gamma': 2.2,
            'unique_signature_hash': 'test',
        }
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash='pattern',
            capture_method='simulated',
            confidence=0.95
        )
        
        formatted = submitter.format_for_rustchain(attestation)
        
        assert formatted['attestation_type'] == 'hardware_crt'
        assert 'crt_fingerprint' in formatted
        assert 'signature' in formatted
    
    def test_attestation_status(self):
        """Test attestation status retrieval"""
        submitter = CRTAttestationSubmitter()
        
        # No attestation yet
        status = submitter.get_attestation_status()
        assert status['status'] == 'no_attestation'
        
        # Create attestation
        fingerprint = {
            'refresh_rate_measured': 60.0,
            'phosphor_decay_ms': 0.033,
            'scanline_jitter_us': 0.5,
            'brightness_nonlinearity_gamma': 2.2,
            'unique_signature_hash': 'test',
        }
        
        attestation = submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash='pattern',
            capture_method='simulated',
            confidence=0.95
        )
        
        status = submitter.get_attestation_status()
        assert status['status'] == 'submitted'


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete flow"""
    
    def test_create_sample_attestation(self):
        """Test sample attestation creation"""
        sample = create_sample_attestation()
        
        assert 'attestation' in sample
        assert 'formatted' in sample
        assert sample['submission_ready'] == True
    
    def test_full_attestation_flow(self):
        """Test complete attestation flow"""
        integration = CRTAttestationIntegration()
        
        result = integration.perform_full_attestation()
        
        assert result['success'] == True
        assert 'stages' in result
        assert 'pattern_generation' in result['stages']
        assert 'capture' in result['stages']
        assert 'analysis' in result['stages']
        assert 'submission' in result['stages']
    
    def test_fingerprint_extraction(self):
        """Test fingerprint extraction for submission"""
        integration = CRTAttestationIntegration()
        
        # Perform attestation
        result = integration.perform_full_attestation()
        
        # Extract fingerprint
        fingerprint = integration.get_crt_fingerprint_for_submission()
        
        assert fingerprint is not None
        assert 'refresh_rate_measured' in fingerprint
        assert 'unique_signature_hash' in fingerprint


# ============================================================================
# CLI Tests
# ============================================================================

class TestCLI:
    """Tests for CLI interface"""
    
    def test_cli_help(self, capsys):
        """Test CLI help output"""
        from crt_cli import main
        
        with pytest.raises(SystemExit):
            sys.argv = ['crt_cli.py', '--help']
            main()
        
        captured = capsys.readouterr()
        assert 'CRT Light Attestation' in captured.out
    
    def test_cli_generate(self, capsys, tmp_path):
        """Test CLI generate command"""
        from crt_cli import main
        
        output_file = tmp_path / "pattern.npy"
        
        sys.argv = [
            'crt_cli.py',
            'generate',
            '--pattern', 'checkered',
            '--width', '320',
            '--height', '240',
            '--output', str(output_file)
        ]
        
        result = main()
        assert result == 0
        assert output_file.exists()
    
    def test_cli_capture_simulated(self, capsys, tmp_path):
        """Test CLI capture command with simulated method"""
        from crt_cli import main
        
        output_file = tmp_path / "capture.json"
        
        sys.argv = [
            'crt_cli.py',
            'capture',
            '--method', 'simulated',
            '--duration', '1',
            '--output', str(output_file)
        ]
        
        result = main()
        assert result == 0
        assert output_file.exists()
    
    def test_cli_analyze(self, capsys, tmp_path):
        """Test CLI analyze command"""
        from crt_cli import main
        
        # First create capture file
        capture_file = tmp_path / "capture.json"
        capture_data = {
            'frames': [
                {'timestamp': i * 0.033, 'mean_intensity': 128 + 50 * np.sin(i)}
                for i in range(60)
            ]
        }
        with open(capture_file, 'w') as f:
            json.dump(capture_data, f)
        
        sys.argv = [
            'crt_cli.py',
            'analyze',
            '--input', str(capture_file)
        ]
        
        result = main()
        assert result == 0
    
    def test_cli_demo(self, capsys):
        """Test CLI demo command"""
        from crt_cli import main
        
        sys.argv = ['crt_cli.py', 'demo']
        result = main()
        
        assert result == 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src', '--cov-report=term-missing'])
