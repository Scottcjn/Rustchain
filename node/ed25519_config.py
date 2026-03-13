#!/usr/bin/env python3
"""
Ed25519 Configuration - Signature Verification Settings
========================================================

RIP-201: Fleet Detection Immune System integration and Ed25519 signature
verification configuration for RustChain.

Features:
    - Fleet immune system integration (optional)
    - Testnet flags for inline public keys and mock signatures
    - Production-safe defaults (all test features disabled)

Security Notes:
    - TESTNET_ALLOW_INLINE_PUBKEY: Disabled in production - inline pubkeys
      bypass key registry validation
    - TESTNET_ALLOW_MOCK_SIG: Disabled in production - mock signatures are
      insecure and should only be used for testing

Integration:
    from ed25519_config import HAVE_FLEET_IMMUNE, TESTNET_ALLOW_INLINE_PUBKEY
    
    if HAVE_FLEET_IMMUNE:
        # Fleet immune system is available
        pass

Author: Elyan Labs
Date: 2026-03
"""

# RIP-201: Fleet Detection Immune System
try:
    from fleet_immune_system import (
        record_fleet_signals, calculate_immune_weights,
        register_fleet_endpoints, ensure_schema as ensure_fleet_schema,
        get_fleet_report
    )
    HAVE_FLEET_IMMUNE = True
    print("[RIP-201] Fleet immune system loaded")
except Exception as _e:
    print(f"[RIP-201] Fleet immune system not available: {_e}")
    HAVE_FLEET_IMMUNE = False


# =============================================================================
# Ed25519 Signature Verification Configuration
# =============================================================================
# The following flags control signature verification behavior for testing and
# production environments. These should be disabled in production to ensure
# proper cryptographic security.
#
# TESTNET_ALLOW_INLINE_PUBKEY: Allows inline public keys for testing (PRODUCTION: Disabled)
# TESTNET_ALLOW_MOCK_SIG: Allows mock signatures for testing (PRODUCTION: Disabled)
# =============================================================================

TESTNET_ALLOW_INLINE_PUBKEY = False  # PRODUCTION: Disabled - Inline pubkeys bypass key registry
TESTNET_ALLOW_MOCK_SIG = False       # PRODUCTION: Disabled - Mock signatures are insecure