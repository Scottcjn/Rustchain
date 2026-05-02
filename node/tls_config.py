"""
Shared TLS configuration for RustChain modules.

Provides consistent TLS certificate verification across all production
code. Uses a pinned certificate at ~/.rustchain/node_cert.pem when
available, otherwise falls back to the system CA bundle.

This eliminates verify=False usage which is vulnerable to MITM attacks.
"""

import os
from typing import Union

# Path to pinned node certificate (self-signed cert for rustchain.org)
_CERT_PATH = os.path.expanduser("~/.rustchain/node_cert.pem")


def get_tls_verify() -> Union[str, bool]:
    """Return the appropriate TLS verify parameter with permission and expiry checks."""
    if os.path.exists(_CERT_PATH):
        # FIX: Security check - Ensure the pinned certificate file is only readable by the owner
        try:
            mode = os.stat(_CERT_PATH).st_mode
            if mode & 0o022:
                import logging
                logging.getLogger("tls.config").warning(f"INSECURE PERMISSIONS on pinned cert {_CERT_PATH}. Fallback to system CA.")
                return True
            
            # FIX: Basic check for certificate expiry if cryptography is available
            try:
                from cryptography import x509
                from datetime import datetime, timezone
                with open(_CERT_PATH, "rb") as f:
                    cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data)
                if cert.not_valid_after_utc < datetime.now(timezone.utc):
                    import logging
                    logging.getLogger("tls.config").error(f"EXPIRED pinned certificate at {_CERT_PATH}. Fallback to system CA.")
                    return True
            except ImportError:
                pass # Cryptography not available, skip expiry check
            except Exception:
                pass # Invalid cert format or other error, fallback managed by requests later
                
            return _CERT_PATH
        except Exception:
            return True
    return True


def get_tls_session(node_url: str = None):
    """Get a requests.Session with proper TLS verification.

    Uses pinned cert if available, otherwise system CA bundle.

    Args:
        node_url: Optional node URL (unused, reserved for future
                  per-node cert pinning).

    Returns:
        requests.Session configured with TLS verification.
    """
    import requests

    session = requests.Session()
    session.verify = get_tls_verify()
    return session


def get_async_tls_verify():
    """Return TLS verify parameter suitable for httpx.AsyncClient.

    Returns the same value as get_tls_verify() — httpx accepts
    the same str/bool types as requests.
    """
    return get_tls_verify()
