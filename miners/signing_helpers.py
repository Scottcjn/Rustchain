# SPDX-License-Identifier: MIT
# Copyright (c) 2025 RustChain Contributors
"""
Shared signing helpers for RustChain miners.

The node verifier (rustchain_v2_integrated_v2.2.1_rip200.py:3949) reconstructs
a pipe-delimited string  miner_id|miner|nonce|commitment  from the attestation
payload and verifies the Ed25519 signature over *that* byte sequence — NOT over
canonical JSON.  Both miners must build the exact same byte string so the
round-trip verifies on the server.

Binding analysis (tri-brain review, PR #6839):
  The pipe message covers miner_id, miner (wallet), nonce, and commitment.
  The commitment itself is  SHA-256(nonce + wallet + json.dumps(entropy, sort_keys=True))
  so the signature transitively covers nonce, wallet, and entropy through the
  commitment hash.  Device / signals / fingerprint fields are carried alongside
  the attestation but are NOT covered by the Ed25519 signature — the server
  validates them via separate checks.  This is unchanged from the pre-fix code;
  the old canonical-JSON signature *did* cover them, but the server never
  verified canonical-JSON signatures (it verified the pipe string), so the
  effective binding surface is the same.
"""


def build_pipe_sign_message(attestation):
    """Build the pipe-delimited signing message from an attestation dict.

    Returns the UTF-8 bytes of  miner_id|miner|nonce|commitment.

    Raises ValueError if any field contains the pipe delimiter ``|`` (which
    would make the message ambiguous on the server side) or if any required
    field is missing.
    """
    try:
        miner_id = attestation["miner_id"]
        miner = attestation["miner"]
        nonce = attestation["nonce"]
        commitment = attestation["report"]["commitment"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"attestation missing required field: {exc}") from exc

    # Delimiter safety — none of the four fields may contain '|'
    for name, value in (("miner_id", miner_id), ("miner", miner),
                        ("nonce", nonce), ("commitment", commitment)):
        if isinstance(value, str) and "|" in value:
            raise ValueError(
                f"attestation field '{name}' contains pipe delimiter: {value!r}"
            )

    msg = f"{miner_id}|{miner}|{nonce}|{commitment}"
    return msg.encode("utf-8")
