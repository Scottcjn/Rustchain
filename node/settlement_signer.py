#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Settlement Signer — Ed25519 treasury key management for claims batch signing.

Loads a treasury private key from a PEM file, signs settlement transaction
payloads, and optionally submits them to a configured node broadcast endpoint.

Environment variables:
  TREASURY_KEY_PATH  — path to Ed25519 PEM private key (default: ./treasury.pem)
  NODE_API_URL       — base URL of RustChain node (default: unset, signing-only)
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Ed25519 dependency (cryptography library)
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PrivateFormat,
        NoEncryption,
        load_pem_private_key,
    )

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TREASURY_KEY_PATH = os.environ.get("TREASURY_KEY_PATH", "treasury.pem")
NODE_API_URL = os.environ.get("NODE_API_URL", "").rstrip("/")


def _load_treasury_key(
    path: Optional[str] = None,
) -> Tuple[bool, Optional[Ed25519PrivateKey], Optional[str]]:
    """Load the treasury Ed25519 private key from a PEM file.

    Returns:
        (success, private_key_or_None, error_or_None)
    """
    if not _HAS_CRYPTO:
        return False, None, (
            "cryptography library required for Ed25519 signing. "
            "Install with: pip install cryptography"
        )

    key_path = Path(path or TREASURY_KEY_PATH)
    if not key_path.exists():
        return False, None, f"Treasury key not found: {key_path}"

    try:
        pem_data = key_path.read_bytes()
        private_key = load_pem_private_key(pem_data, password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            return False, None, "Key file does not contain an Ed25519 private key"
        return True, private_key, None
    except Exception as e:
        return False, None, f"Failed to load treasury key: {e}"


def _build_settlement_message(tx_data: dict) -> bytes:
    """Build a canonical message to sign for a settlement batch.

    The message includes the batch id, each output recipient and amount,
    the fee, and a timestamp to prevent replay across batches.
    """
    payload = {
        "batch_id": tx_data["batch_id"],
        "outputs": [
            {"address": o["address"], "amount_urtc": o["amount_urtc"]}
            for o in tx_data.get("outputs", [])
        ],
        "fee_urtc": tx_data.get("fee_urtc", 0),
        "total_amount_urtc": tx_data.get("total_amount_urtc", 0),
        "created_at": tx_data.get("created_at", int(time.time())),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_settlement_batch(
    tx_data: dict,
    key_path: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Sign a settlement batch with the treasury key.

    Args:
        tx_data: Transaction data dict (batch_id, outputs, fee, etc.)
        key_path: Optional override for treasury key path

    Returns:
        (success, signature_hex_or_tx_hash, error_or_None)

    On success, returns the Ed25519 signature as hex in the second element.
    This serves as the transaction identifier (tx_hash) since the signature
    uniquely commits to the batch data — no separate blockchain hash needed
    until a full node broadcast endpoint exists.
    """
    success, private_key, error = _load_treasury_key(key_path)
    if not success:
        return False, None, error

    try:
        message = _build_settlement_message(tx_data)
        signature = private_key.sign(message)
        tx_hash = "0x" + signature.hex()
        return True, tx_hash, None
    except Exception as e:
        return False, None, f"Signing failed: {e}"


def generate_keypair(output_path: str) -> Tuple[bool, Optional[str]]:
    """Generate a new Ed25519 treasury keypair and save to PEM.

    Args:
        output_path: Path to save the private key PEM file

    Returns:
        (success, error_or_None)
    """
    if not _HAS_CRYPTO:
        return False, (
            "cryptography library required. Install with: pip install cryptography"
        )

    try:
        private_key = Ed25519PrivateKey.generate()
        pem_data = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(pem_data)
        out.chmod(0o600)

        public_key = private_key.public_key()
        from cryptography.hazmat.primitives.serialization import PublicFormat

        pub_pem = public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        pub_path = out.with_suffix(".pub")
        pub_path.write_text(pub_pem.hex() + "\n")

        logger.info(f"Generated treasury keypair: {output_path}")
        logger.info(f"Public key (hex): {pub_pem.hex()}")
        return True, None
    except Exception as e:
        return False, f"Failed to generate keypair: {e}"
