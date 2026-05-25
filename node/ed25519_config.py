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
# These flags are resolved from environment variables at attribute-read time
# so they cannot be bypassed by monkey-patching module-level constants.
#
# Set RUSTCHAIN_ALLOW_INLINE_PUBKEY=1 or RUSTCHAIN_ALLOW_MOCK_SIG=1 to
# enable test-mode behavior.  Default (unset / any other value) = disabled.
#
# !!! Setting integrated_node.TESTNET_ALLOW_MOCK_SIG = True has NO effect.
#     The module __setattr__ raises AttributeError with a clear message.
# =============================================================================

import os as _os


def _allow_inline_pubkey() -> bool:
    return _os.environ.get("RUSTCHAIN_ALLOW_INLINE_PUBKEY", "0") == "1"


def _allow_mock_sig() -> bool:
    return _os.environ.get("RUSTCHAIN_ALLOW_MOCK_SIG", "0") == "1"


def __getattr__(name: str):
    """Resolve TESTNET_ALLOW_MOCK_SIG / TESTNET_ALLOW_INLINE_PUBKEY
    from environment variables at read time, not from mutable module state."""
    if name == "TESTNET_ALLOW_MOCK_SIG":
        return _allow_mock_sig()
    if name == "TESTNET_ALLOW_INLINE_PUBKEY":
        return _allow_inline_pubkey()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):
    """Prevent monkey-patching of security-critical config flags."""
    if name in ("TESTNET_ALLOW_MOCK_SIG", "TESTNET_ALLOW_INLINE_PUBKEY"):
        raise AttributeError(
            f"Cannot set {name!r} — this flag is read-only from env var. "
            f"Set RUSTCHAIN_ALLOW_MOCK_SIG or RUSTCHAIN_ALLOW_INLINE_PUBKEY "
            f"in the environment instead."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
