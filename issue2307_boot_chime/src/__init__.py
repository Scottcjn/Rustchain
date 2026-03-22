"""
Boot Chime Proof-of-Iron — Acoustic Hardware Attestation

This module provides hardware attestation through acoustic fingerprinting,
analyzing unique sound signatures produced by hardware during boot sequences.

Issue: #2307
Author: Qwen Code Assistant
Date: 2026-03-22
"""

from .acoustic_fingerprint import AcousticFingerprint
from .boot_chime_capture import BootChimeCapture
from .proof_of_iron import ProofOfIron, ProofOfIronError
from .spectral_analysis import SpectralAnalyzer

__version__ = "1.0.0"
__all__ = [
    "AcousticFingerprint",
    "BootChimeCapture",
    "ProofOfIron",
    "ProofOfIronError",
    "SpectralAnalyzer",
]
