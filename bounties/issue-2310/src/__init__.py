"""
CRT Light Attestation - RustChain Security by Cathode Ray

This package provides practical CRT-based hardware attestation for RustChain.
"""

__version__ = '1.0.0'
__author__ = 'RustChain Bounty Program'

from .crt_pattern_generator import CRTPatternGenerator
from .crt_capture import CRTCapture, CaptureConfig, CaptureMethod
from .crt_analyzer import CRTAnalyzer, CRTFingerprint
from .crt_attestation_submitter import CRTAttestationSubmitter, CRTAttestation

__all__ = [
    'CRTPatternGenerator',
    'CRTCapture',
    'CaptureConfig',
    'CaptureMethod',
    'CRTAnalyzer',
    'CRTFingerprint',
    'CRTAttestationSubmitter',
    'CRTAttestation',
]
