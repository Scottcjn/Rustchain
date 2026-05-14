"""
CRT Light Attestation - RustChain Security by Cathode Ray

This package provides practical CRT-based hardware attestation for RustChain.
"""

import importlib

__version__ = '1.0.0'
__author__ = 'RustChain Bounty Program'

_EXPORT_MODULES = {
    'CRTPatternGenerator': 'crt_pattern_generator',
    'CRTCapture': 'crt_capture',
    'CaptureConfig': 'crt_capture',
    'CaptureMethod': 'crt_capture',
    'CRTAnalyzer': 'crt_analyzer',
    'CRTFingerprint': 'crt_analyzer',
    'CRTAttestationSubmitter': 'crt_attestation_submitter',
    'CRTAttestation': 'crt_attestation_submitter',
}


def __getattr__(name):
    """Lazily load CRT components while supporting package-relative imports."""
    if name not in _EXPORT_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name = _EXPORT_MODULES[name]
    if __package__:
        module = importlib.import_module(f".{module_name}", __name__)
    else:
        module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value

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
