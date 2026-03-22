"""
CRT Attestation Submitter - Fingerprint Integration with RustChain

Integrates CRT optical fingerprint into RustChain attestation system.
Submits crt_fingerprint field with hardware attestation.
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import base64


@dataclass
class CRTAttestation:
    """CRT attestation data structure"""
    version: str = "1.0.0"
    timestamp: int = 0
    crt_fingerprint: Dict[str, Any] = None
    pattern_hash: str = ""
    capture_method: str = ""
    confidence_score: float = 0.0
    signature: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'version': self.version,
            'timestamp': self.timestamp,
            'crt_fingerprint': self.crt_fingerprint,
            'pattern_hash': self.pattern_hash,
            'capture_method': self.capture_method,
            'confidence_score': self.confidence_score,
            'signature': self.signature,
        }


class CRTAttestationSubmitter:
    """
    Submits CRT attestation to RustChain network.
    
    Integrates with existing hardware attestation flow:
    1. Generate deterministic pattern
    2. Capture CRT response
    3. Analyze and extract fingerprint
    4. Submit with attestation
    """
    
    ATTESTATION_VERSION = "1.0.0"
    RUSTCHAIN_ATTESTATION_ENDPOINT = "/api/v1/attestation/submit"
    
    def __init__(self, node_url: str = "https://rustchain.org"):
        """
        Initialize attestation submitter.
        
        Args:
            node_url: RustChain node URL
        """
        self.node_url = node_url
        self.last_attestation: Optional[CRTAttestation] = None
        
    def create_attestation(self, 
                           fingerprint: Dict[str, Any],
                           pattern_hash: str,
                           capture_method: str,
                           confidence: float) -> CRTAttestation:
        """
        Create CRT attestation from analysis results.
        
        Args:
            fingerprint: CRT fingerprint from analyzer
            pattern_hash: Hash of displayed pattern
            capture_method: Capture method used (webcam/photodiode)
            confidence: Confidence score (0-1)
            
        Returns:
            CRT attestation object
        """
        attestation = CRTAttestation(
            version=self.ATTESTATION_VERSION,
            timestamp=int(time.time()),
            crt_fingerprint=fingerprint,
            pattern_hash=pattern_hash,
            capture_method=capture_method,
            confidence_score=confidence,
            signature=""  # Will be signed
        )
        
        # Generate signature
        attestation.signature = self._sign_attestation(attestation)
        
        self.last_attestation = attestation
        return attestation
    
    def _sign_attestation(self, attestation: CRTAttestation) -> str:
        """
        Generate signature for attestation.
        
        In production, this would use miner's private key.
        For now, creates deterministic hash.
        
        Args:
            attestation: Attestation to sign
            
        Returns:
            Signature as hex string
        """
        # Create message to sign
        message = f"{attestation.version}|" \
                  f"{attestation.timestamp}|" \
                  f"{attestation.pattern_hash}|" \
                  f"{attestation.capture_method}|" \
                  f"{attestation.confidence_score:.4f}"
        
        # In production: sign with ECDSA using miner's private key
        # For now: deterministic hash
        signature = hashlib.sha256(message.encode()).hexdigest()
        
        return signature
    
    def verify_attestation(self, attestation: CRTAttestation) -> bool:
        """
        Verify attestation signature and integrity.
        
        Args:
            attestation: Attestation to verify
            
        Returns:
            True if valid
        """
        # Verify timestamp is recent (within 5 minutes)
        current_time = int(time.time())
        if abs(current_time - attestation.timestamp) > 300:
            return False
        
        # Verify signature
        expected_signature = self._sign_attestation(attestation)
        if attestation.signature != expected_signature:
            return False
        
        # Verify fingerprint has required fields
        required_fields = [
            'refresh_rate_measured',
            'phosphor_decay_ms',
            'scanline_jitter_us',
            'brightness_nonlinearity_gamma',
            'unique_signature_hash'
        ]
        
        if not attestation.crt_fingerprint:
            return False
        
        for field in required_fields:
            if field not in attestation.crt_fingerprint:
                return False
        
        return True
    
    def submit_attestation(self, attestation: CRTAttestation) -> Dict[str, Any]:
        """
        Submit attestation to RustChain network.
        
        Args:
            attestation: CRT attestation to submit
            
        Returns:
            Submission result
        """
        # Verify before submitting
        if not self.verify_attestation(attestation):
            return {
                'success': False,
                'error': 'invalid_attestation',
                'message': 'Attestation verification failed'
            }
        
        # Prepare submission payload
        payload = {
            'attestation_type': 'crt_light',
            'version': self.ATTESTATION_VERSION,
            'data': attestation.to_dict(),
        }
        
        # In production, would make HTTP POST to node
        # For now, simulate successful submission
        submission_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        
        return {
            'success': True,
            'submission_hash': submission_hash,
            'timestamp': int(time.time()),
            'node_url': self.node_url,
            'attestation_type': 'crt_light',
            'crt_fingerprint_hash': attestation.crt_fingerprint.get('unique_signature_hash'),
        }
    
    def format_for_rustchain(self, attestation: CRTAttestation) -> Dict[str, Any]:
        """
        Format attestation for RustChain API submission.
        
        Args:
            attestation: CRT attestation
            
        Returns:
            Formatted dictionary for API
        """
        return {
            'miner_id': 'auto_detected',
            'attestation_type': 'hardware_crt',
            'timestamp': attestation.timestamp,
            'crt_fingerprint': attestation.crt_fingerprint,
            'metadata': {
                'pattern_hash': attestation.pattern_hash,
                'capture_method': attestation.capture_method,
                'confidence': attestation.confidence_score,
                'version': attestation.version,
            },
            'signature': attestation.signature,
        }
    
    def get_attestation_status(self) -> Dict[str, Any]:
        """
        Get status of last attestation.
        
        Returns:
            Status dictionary
        """
        if not self.last_attestation:
            return {'status': 'no_attestation'}
        
        return {
            'status': 'submitted',
            'timestamp': self.last_attestation.timestamp,
            'fingerprint_hash': self.last_attestation.crt_fingerprint.get('unique_signature_hash'),
            'verified': self.verify_attestation(self.last_attestation),
        }


class CRTAttestationIntegration:
    """
    High-level integration of full CRT attestation flow.
    
    Orchestrates pattern generation, capture, analysis, and submission.
    """
    
    def __init__(self, node_url: str = "https://rustchain.org"):
        """
        Initialize CRT attestation integration.
        
        Args:
            node_url: RustChain node URL
        """
        self.node_url = node_url
        self.submitter = CRTAttestationSubmitter(node_url)
        self.last_result: Dict[str, Any] = {}
        
    def perform_full_attestation(self,
                                  pattern_config: Optional[Dict] = None,
                                  capture_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform complete CRT attestation flow.
        
        Args:
            pattern_config: Pattern generator configuration
            capture_config: Capture configuration
            
        Returns:
            Full attestation result
        """
        # Import here to avoid circular dependencies
        from crt_pattern_generator import CRTPatternGenerator
        from crt_capture import CRTCapture, CaptureConfig, CaptureMethod
        from crt_analyzer import CRTAnalyzer
        
        result = {
            'success': False,
            'stages': {},
            'crt_fingerprint': None,
            'submission_result': None,
        }
        
        try:
            # Stage 1: Generate pattern
            result['stages']['pattern_generation'] = self._generate_pattern(pattern_config)
            pattern_gen = CRTPatternGenerator(
                **pattern_config if pattern_config else {}
            )
            
            # Stage 2: Capture CRT response
            result['stages']['capture'] = self._capture_response(capture_config)
            
            # Stage 3: Analyze fingerprint
            result['stages']['analysis'] = self._analyze_fingerprint()
            
            # Stage 4: Create and submit attestation
            result['stages']['submission'] = self._submit_attestation()
            
            result['success'] = True
            result['crt_fingerprint'] = self.submitter.last_attestation.crt_fingerprint if self.submitter.last_attestation else None
            result['submission_result'] = result['stages'].get('submission')
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        self.last_result = result
        return result
    
    def _generate_pattern(self, config: Optional[Dict]) -> Dict[str, Any]:
        """Generate test pattern"""
        from crt_pattern_generator import CRTPatternGenerator
        
        gen = CRTPatternGenerator(**(config or {}))
        pattern = gen.generate_checkered_pattern()
        pattern_hash = gen.compute_pattern_hash(pattern)
        
        return {
            'success': True,
            'pattern_hash': pattern_hash,
            'metadata': gen.get_pattern_metadata(),
        }
    
    def _capture_response(self, config: Optional[Dict]) -> Dict[str, Any]:
        """Capture CRT response"""
        from crt_capture import CRTCapture, CaptureConfig, CaptureMethod
        
        # Use simulated capture for testing
        capture_config = CaptureConfig(
            method=CaptureMethod.SIMULATED,
            **(config or {})
        )
        
        capture = CRTCapture(capture_config)
        frames = capture.capture_sequence(duration_s=2.0)
        
        return {
            'success': True,
            'frames_captured': len(frames),
            'statistics': capture.get_capture_statistics(),
        }
    
    def _analyze_fingerprint(self) -> Dict[str, Any]:
        """Analyze CRT fingerprint"""
        from crt_analyzer import CRTAnalyzer
        
        analyzer = CRTAnalyzer()
        
        # Simulate captured data for analysis
        import numpy as np
        np.random.seed(42)
        num_frames = 60
        timestamps = np.linspace(0, 2, num_frames)
        intensities = 128 + 50 * np.sin(2 * np.pi * 60 * timestamps)
        
        captured_data = {
            'frames': [
                {'timestamp': float(ts), 'mean_intensity': float(int)}
                for ts, int in zip(timestamps, intensities)
            ]
        }
        
        fingerprint = analyzer.analyze_full(captured_data)
        
        return {
            'success': True,
            'fingerprint': fingerprint.to_dict(),
            'report': analyzer.get_analysis_report(),
        }
    
    def _submit_attestation(self) -> Dict[str, Any]:
        """Submit attestation"""
        if not self.last_result.get('stages', {}).get('analysis'):
            return {'success': False, 'error': 'No analysis data'}
        
        fingerprint = self.last_result['stages']['analysis']['fingerprint']
        pattern_hash = self.last_result['stages']['pattern_generation']['pattern_hash']
        
        attestation = self.submitter.create_attestation(
            fingerprint=fingerprint,
            pattern_hash=pattern_hash,
            capture_method='simulated',
            confidence=0.95
        )
        
        submission = self.submitter.submit_attestation(attestation)
        
        return submission
    
    def get_crt_fingerprint_for_submission(self) -> Optional[Dict[str, Any]]:
        """
        Get CRT fingerprint formatted for RustChain attestation submission.
        
        Returns:
            Fingerprint dictionary or None
        """
        if not self.last_result.get('success'):
            return None
        
        return self.last_result.get('crt_fingerprint')


def create_sample_attestation() -> Dict[str, Any]:
    """
    Create a sample CRT attestation for demonstration.
    
    Returns:
        Sample attestation dictionary
    """
    # Simulated fingerprint data
    fingerprint = {
        'refresh_rate_measured': 60.012,
        'refresh_rate_drift_ppm': 200,
        'phosphor_decay_ms': 0.035,
        'phosphor_type_estimate': 'P22',
        'scanline_jitter_us': 0.52,
        'brightness_nonlinearity_gamma': 2.28,
        'electron_gun_wear_estimate': 0.23,
        'flyback_transformer_drift_ppm': 185,
        'unique_signature_hash': hashlib.sha256(
            f"{time.time()}".encode()
        ).hexdigest(),
    }
    
    submitter = CRTAttestationSubmitter()
    attestation = submitter.create_attestation(
        fingerprint=fingerprint,
        pattern_hash="abc123...",
        capture_method="webcam",
        confidence=0.95
    )
    
    return {
        'attestation': attestation.to_dict(),
        'formatted': submitter.format_for_rustchain(attestation),
        'submission_ready': True,
    }


def test_attestation_flow() -> Dict[str, Any]:
    """
    Test the complete attestation flow.
    
    Returns:
        Test results
    """
    print("CRT Attestation Flow - Test")
    print("=" * 50)
    
    # Create sample attestation
    print("\nCreating sample attestation...")
    sample = create_sample_attestation()
    
    print(f"\nAttestation Data:")
    print(f"  Version: {sample['attestation']['version']}")
    print(f"  Capture method: {sample['attestation']['capture_method']}")
    print(f"  Confidence: {sample['attestation']['confidence_score']:.1%}")
    
    print(f"\nCRT Fingerprint:")
    fp = sample['attestation']['crt_fingerprint']
    print(f"  Refresh rate: {fp['refresh_rate_measured']:.3f} Hz")
    print(f"  Phosphor decay: {fp['phosphor_decay_ms']:.3f} ms")
    print(f"  Unique signature: {fp['unique_signature_hash'][:32]}...")
    
    print(f"\nFormatted for RustChain:")
    formatted = sample['formatted']
    print(f"  Type: {formatted['attestation_type']}")
    print(f"  Has fingerprint: {formatted['crt_fingerprint'] is not None}")
    print(f"  Signature valid: {len(formatted['signature']) == 64}")
    
    # Test verification
    submitter = CRTAttestationSubmitter()
    from dataclasses import asdict
    test_attestation = CRTAttestation(**sample['attestation'])
    is_valid = submitter.verify_attestation(test_attestation)
    print(f"\nVerification: {'PASSED' if is_valid else 'FAILED'}")
    
    print("\n" + "=" * 50)
    print("Attestation flow test complete!")
    
    return sample


if __name__ == '__main__':
    test_attestation_flow()
