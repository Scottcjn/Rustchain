"""
RustChain TLS Configuration
Centralizes TLS verification settings to avoid hardcoded verify=False.
"""
import os

# Default: verify TLS certificates (secure)
# Set RUSTCHAIN_TLS_VERIFY=false for local dev with self-signed certs
TLS_VERIFY = os.getenv('RUSTCHAIN_TLS_VERIFY', 'true').lower() != 'false'

# Optional: custom CA bundle path
CA_BUNDLE = os.getenv('RUSTCHAIN_CA_BUNDLE', None)


def get_verify():
    """Return the verify parameter for requests calls."""
    if CA_BUNDLE:
        return CA_BUNDLE
    return TLS_VERIFY
