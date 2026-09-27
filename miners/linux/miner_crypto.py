#!/usr/bin/env python3
"""
RustChain Miner Cryptographic Module — Lightweight Ed25519
==========================================================
Provides real Ed25519 signing for attestation payloads.
Replaces the sha512(message+wallet) pseudo-signature.

Dependencies:
  pip install PyNaCl   (or: apt install python3-nacl)

Keystore: ~/.rustchain/miner_key.json (XOR-obscured with a per-machine key)

Keystore key derivation (see _get_machine_entropy):
  - Windows: HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid
  - Linux:   /etc/machine-id or /var/lib/dbus/machine-id
  - macOS:   IOPlatformUUID ("Hardware UUID" from system_profiler)
  - Otherwise: RUSTCHAIN_KEYSTORE_PASSPHRASE (PBKDF2-derived) must be set.
There is NO constant fallback: if no identifier and no passphrase is
available, keystore operations raise KeystoreKeyUnavailable.

Legacy migration: keystores written before this fix on hosts with no
machine identifier (all Windows installs) were obscured with the public
constant sha256("fallback-no-machine-id"). load_keystore() tries the real
key first; only if that does not reproduce the stored public key does it
try the legacy constant (read-only), and on success it immediately
rewrites the keystore with the real key and prints a warning.
"""

import hashlib
import json
import os
import sys
import time

# Try PyNaCl first (preferred), fall back to pure-Python ed25519
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import HexEncoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False

KEYSTORE_DIR = os.path.expanduser("~/.rustchain")
KEYSTORE_FILE = os.path.join(KEYSTORE_DIR, "miner_key.json")


PASSPHRASE_ENV = "RUSTCHAIN_KEYSTORE_PASSPHRASE"

# The pre-fix code silently used this constant when no machine identifier was
# found (every Windows install). It is public, so a keystore obscured with it
# is effectively plaintext. Kept ONLY so old keystores can be read once and
# migrated -- never used to write.
_LEGACY_FALLBACK_ENTROPY = hashlib.sha256(b"fallback-no-machine-id").digest()


class KeystoreKeyUnavailable(RuntimeError):
    """No per-machine identifier or passphrase is available to key the keystore."""


def _read_windows_machine_guid() -> str:
    """Return HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid, or ""."""
    try:
        import winreg
    except ImportError:
        return ""
    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            access,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except OSError:
        return ""
    return str(value).strip()


def _get_machine_entropy() -> bytes:
    """Get machine-specific entropy for keystore encryption seed.

    Raises KeystoreKeyUnavailable instead of ever falling back to a constant.
    """
    parts = []
    # Windows MachineGuid (unique per installation)
    if sys.platform == "win32":
        guid = _read_windows_machine_guid()
        if guid:
            parts.append(guid)
    # machine-id (Linux)
    if not parts:
        for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            try:
                with open(path, "r") as f:
                    value = f.read().strip()
            except OSError:
                continue
            if value:
                parts.append(value)
                break
    # macOS hardware UUID
    if not parts and sys.platform == "darwin":
        try:
            import subprocess
            out = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                if "UUID" in line:
                    value = line.split(":")[-1].strip()
                    if value:
                        parts.append(value)
                    break
        except Exception:
            pass
    if parts:
        return hashlib.sha256("|".join(parts).encode()).digest()
    # No machine identifier: require an explicit user passphrase.
    passphrase = os.environ.get(PASSPHRASE_ENV, "")
    if passphrase:
        return hashlib.pbkdf2_hmac(
            "sha256", passphrase.encode("utf-8"),
            b"rustchain-miner-keystore-v1", 200_000,
        )
    raise KeystoreKeyUnavailable(
        "No machine identifier found (Windows MachineGuid, /etc/machine-id, "
        "/var/lib/dbus/machine-id, or macOS IOPlatformUUID) to protect the "
        f"miner keystore. Set the {PASSPHRASE_ENV} environment variable to a "
        "strong passphrase (and keep it set on every run) to continue."
    )


def _xor32(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, key))


def _pubkey_for(private_key_hex: str) -> str:
    sk = SigningKey(bytes.fromhex(private_key_hex))
    return sk.verify_key.encode(encoder=HexEncoder).decode()


def _write_keystore(keypair: dict, path: str, entropy: bytes) -> None:
    """Atomically write a version-1 keystore obscured with ``entropy``."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    pk_bytes = bytes.fromhex(keypair["private_key"])
    data = {
        "version": 1,
        "public_key": keypair["public_key"],
        "obscured_private": _xor32(pk_bytes, entropy).hex(),
    }
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


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
    entropy = _get_machine_entropy()  # raises rather than using a constant
    _write_keystore(keypair, path, entropy)
    print(f"[CRYPTO] Keypair saved to {path}")


def load_keystore(path: str = KEYSTORE_FILE) -> dict:
    """Load keypair from disk.

    Tries the real per-machine key first. If that does not reproduce the
    stored public key, tries the legacy constant fallback key (read-only);
    on success the keystore is re-written with the real key.
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        data = json.load(f)
    if data.get("version") != 1:
        return {}
    entropy = _get_machine_entropy()  # raises rather than using a constant
    obscured = bytes.fromhex(data["obscured_private"])
    public_key = data["public_key"]
    candidate = {"private_key": _xor32(obscured, entropy).hex(), "public_key": public_key}
    if not NACL_AVAILABLE:
        # Cannot verify which key was used; return the real-key result only.
        return candidate
    try:
        if _pubkey_for(candidate["private_key"]) == public_key:
            return candidate
    except Exception:
        pass
    # Legacy keystore written with the public constant fallback key.
    legacy = {"private_key": _xor32(obscured, _LEGACY_FALLBACK_ENTROPY).hex(),
              "public_key": public_key}
    try:
        legacy_ok = _pubkey_for(legacy["private_key"]) == public_key
    except Exception:
        legacy_ok = False
    if legacy_ok:
        _write_keystore(legacy, path, entropy)
        print(
            "[CRYPTO] WARNING: keystore at "
            f"{path} was protected with a publicly known constant key "
            "(pre-fix fallback). It has been re-encrypted with this machine's "
            "key. Anyone who copied the old file could recover the private key; "
            "consider rotating your miner key if the file may have been exposed."
        )
        return legacy
    # Neither key reproduces the public key: return the real-key attempt so
    # the caller's validation reports it as corrupted.
    return candidate


def get_or_create_keypair(path: str = KEYSTORE_FILE) -> dict:
    """Load existing keypair or generate a new one."""
    existing = load_keystore(path)
    if existing and existing.get("private_key"):
        # Validate the key loads correctly
        try:
            if _pubkey_for(existing["private_key"]) == existing["public_key"]:
                return existing
        except Exception:
            pass
        # Keep the undecryptable keystore instead of silently destroying it.
        backup = f"{path}.unreadable-{int(time.time())}"
        os.replace(path, backup)
        print(f"[CRYPTO] Existing key could not be decrypted; moved to {backup}, generating new one")
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


def address_from_pubkey(public_key_hex: str) -> str:
    """Derive the canonical RTC identity controlled by an Ed25519 public key."""
    public_key = bytes.fromhex(public_key_hex)
    if len(public_key) != 32:
        raise ValueError("Ed25519 public key must be exactly 32 bytes")
    return f"RTC{hashlib.sha256(public_key).hexdigest()[:40]}"


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
