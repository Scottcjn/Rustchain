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
    """Return the appropriate TLS verify parameter for requests/httpx.

    Returns:
        str: Path to pinned cert file if it exists.
        bool: True to use system CA bundle as fallback.
    """
    if os.path.exists(_CERT_PATH):
        return _CERT_PATH
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
