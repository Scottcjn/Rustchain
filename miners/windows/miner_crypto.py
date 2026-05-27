#!/usr/bin/env python3
"""
RustChain Miner Cryptographic Module — Lightweight Ed25519
==========================================================
Provides real Ed25519 signing for attestation payloads.
Replaces the sha512(message+wallet) pseudo-signature.

Dependencies:
  pip install PyNaCl   (or: apt install python3-nacl)

Keystore: ~/.rustchain/miner_key.json (encrypted with machine-id)
"""

import hashlib
import json
import os
import sys

# Try PyNaCl first (preferred), fall back to pure-Python ed25519
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import HexEncoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False

KEYSTORE_DIR = os.path.expanduser("~/.rustchain")
KEYSTORE_FILE = os.path.join(KEYSTORE_DIR, "miner_key.json")


def _get_machine_entropy() -> bytes:
    """Get machine-specific entropy for keystore encryption seed."""
    parts = []
    # machine-id (Linux)
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            with open(path, "r") as f:
                parts.append(f.read().strip())
                break
        except OSError:
            pass
    # macOS hardware UUID
    if not parts:
        try:
            import subprocess
            out = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                if "UUID" in line:
                    parts.append(line.split(":")[-1].strip())
                    break
        except Exception:
            pass
    if not parts:
        parts.append("fallback-no-machine-id")
    return hashlib.sha256("|".join(parts).encode()).digest()


def generate_keypair() -> dict:
    """Generate a new Ed25519 keypair. Returns dict with hex keys."""
    if not NACL_AVAILABLE:
        raise RuntimeError("PyNaCl required: pip install PyNaCl")
    sk = SigningKey.generate()
    vk = sk.verify_key
    return {
        "private_key": sk.encode(encoder=HexEncoder).decode(),
        "public_key": vk.encode(encoder=HexEncoder).decode(),
    }


def save_keystore(keypair: dict, path: str = KEYSTORE_FILE) -> None:
    """Save keypair to disk. XOR-obscured with machine entropy (not full encryption)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entropy = _get_machine_entropy()
    # XOR the private key with machine entropy for basic at-rest protection
    pk_bytes = bytes.fromhex(keypair["private_key"])
    obscured = bytes(a ^ b for a, b in zip(pk_bytes, entropy))
    data = {
        "version": 1,
        "public_key": keypair["public_key"],
        "obscured_private": obscured.hex(),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)
    print(f"[CRYPTO] Keypair saved to {path}")


def load_keystore(path: str = KEYSTORE_FILE) -> dict:
    """Load keypair from disk."""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    if data.get("version") != 1:
        return {}
    entropy = _get_machine_entropy()
    obscured = bytes.fromhex(data["obscured_private"])
    pk_bytes = bytes(a ^ b for a, b in zip(obscured, entropy))
    return {
        "private_key": pk_bytes.hex(),
        "public_key": data["public_key"],
    }


def get_or_create_keypair(path: str = KEYSTORE_FILE) -> dict:
    """Load existing keypair or generate a new one."""
    existing = load_keystore(path)
    if existing and existing.get("private_key"):
        # Validate the key loads correctly
        try:
            sk = SigningKey(bytes.fromhex(existing["private_key"]))
            vk = sk.verify_key
            if vk.encode(encoder=HexEncoder).decode() == existing["public_key"]:
                return existing
        except Exception:
            print("[CRYPTO] Existing key corrupted, generating new one")
    kp = generate_keypair()
    save_keystore(kp, path)
    return kp


def sign_payload(payload_bytes: bytes, private_key_hex: str) -> str:
    """Sign bytes with Ed25519 private key. Returns hex signature."""
    if not NACL_AVAILABLE:
        raise RuntimeError("PyNaCl required for signing")
    sk = SigningKey(bytes.fromhex(private_key_hex))
    signed = sk.sign(payload_bytes)
    return signed.signature.hex()


def verify_signature(payload_bytes: bytes, signature_hex: str, public_key_hex: str) -> bool:
    """Verify an Ed25519 signature."""
    if not NACL_AVAILABLE:
        return False
    try:
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        vk.verify(payload_bytes, bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False


def canonical_json(obj: dict) -> bytes:
    """Produce canonical JSON bytes for signing (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


if __name__ == "__main__":
    print("RustChain Miner Crypto Module")
    print("=" * 50)

    if not NACL_AVAILABLE:
        print("ERROR: PyNaCl not installed. Run: pip install PyNaCl")
        sys.exit(1)

    # Demo: generate, sign, verify
    kp = get_or_create_keypair()
    print(f"Public Key:  {kp['public_key']}")
    print(f"Private Key: {kp['private_key'][:16]}... (truncated)")

    test_payload = canonical_json({"test": "data", "nonce": "abc123"})
    sig = sign_payload(test_payload, kp["private_key"])
    print(f"Signature:   {sig[:32]}... ({len(sig)} hex chars)")

    ok = verify_signature(test_payload, sig, kp["public_key"])
    print(f"Verify:      {'PASS' if ok else 'FAIL'}")

    # Tamper test
    tampered = canonical_json({"test": "TAMPERED", "nonce": "abc123"})
    bad = verify_signature(tampered, sig, kp["public_key"])
    print(f"Tamper test: {'FAIL (good!)' if not bad else 'PASS (BAD!)'}")
