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