"""
Provenance Receipt — generates cryptographically signed receipts for completed sessions.
Uses Ed25519 signing so anyone can verify a receipt was genuinely produced by the machine.
"""
import json
import time
import hashlib
import base64
import struct
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List
from pathlib import Path

# Ed25519 support — try libsodium / pynacl first, fall back to ed25519 package
try:
    from nacl.signing import SigningKey
    from nacl.encoding import RawEncoder
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

try:
    import ed25519
    HAS_ED25519 = True
except ImportError:
    HAS_ED25519 = False


def _generate_keypair() -> tuple:
    """Generate a new Ed25519 keypair. Returns (signing_key_hex, verify_key_hex)."""
    if HAS_NACL:
        sk = SigningKey.generate()
        vk = sk.verify_key
        return base64.b16encode(sk.encode()).decode().lower(), base64.b16encode(vk.encode()).decode().lower()
    elif HAS_ED25519:
        sk = ed25519.SigningKey.generate()
        vk = sk.get_verifying_key()
        return sk.to_bytes().hex(), vk.to_bytes().hex()
    else:
        # Fallback: deterministic keys from hash (NOT secure — demo only)
        import secrets
        seed = secrets.token_bytes(32)
        return seed.hex(), hashlib.sha256(seed).hexdigest()


@dataclass
class ProvenanceReceipt:
    """
    A signed provenance receipt for a completed relic rental session.
    Contains machine passport, session details, output hash, and Ed25519 signature.
    """
    version: str = "1.0"
    receipt_id: str          # Unique receipt identifier
    machine_passport_id: str # Machine NFT token ID / name
    machine_model: str
    session_id: str
    renter: str
    slot_hours: int
    start_time: float
    end_time: float
    duration_seconds: int
    output_hash: str          # SHA-256 of the computed output
    attestation_proof: str     # Hardware attestation data
    ed25519_pubkey: str       # Machine's Ed25519 public key
    signature: str            # Ed25519 signature over the receipt payload
    signed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """Return a dict representation suitable for JSON serialization."""
        d = asdict(self)
        d["start_time_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.start_time))
        d["end_time_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.end_time))
        d["signed_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.signed_at))
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def verify(self) -> bool:
        """
        Verify the Ed25519 signature on this receipt.
        The signature must be over the canonical JSON of the receipt (excluding signature field).
        """
        if not self.signature:
            return False
        payload = self._canonical_json()
        return self._ed25519_verify(payload, self.signature, self.ed25519_pubkey)

    def _canonical_json(self) -> bytes:
        """Canonical JSON representation (excludes signature, signed_at)."""
        d = self.to_dict()
        d.pop("signature", None)
        d.pop("signed_at", None)
        d.pop("signed_at_iso", None)
        canonical = json.dumps(d, separators=(",", ":"), sort_keys=True)
        return canonical.encode("utf-8")

    @staticmethod
    def _ed25519_verify(message: bytes, signature_hex: str, pubkey_hex: str) -> bool:
        """Verify an Ed25519 signature."""
        try:
            sig_bytes = bytes.fromhex(signature_hex)
            vk_bytes = bytes.fromhex(pubkey_hex)
        except Exception:
            return False

        if HAS_NACL:
            try:
                vk = nacl.signing.VerifyKey(vk_bytes, encoder=RawEncoder)
                vk.verify(message, sig_bytes)
                return True
            except Exception:
                return False
        elif HAS_ED25519:
            try:
                vk = ed25519.VerifyingKey(vk_bytes)
                vk.verify(sig_bytes, message)
                return True
            except Exception:
                return False
        else:
            # Fallback verification (demo only — accepts any well-formed sig)
            return len(sig_bytes) == 64


class ProvenanceReceiptManager:
    """
    Creates and stores provenance receipts locally.
    Each machine has its own Ed25519 keypair (stored in keys/<machine_passport_id>.key).
    """

    KEY_DIR = Path(__file__).parent / "keys"
    RECEIPTS_DIR = Path(__file__).parent / "receipts"

    def __init__(self):
        self.KEY_DIR.mkdir(exist_ok=True)
        self.RECEIPTS_DIR.mkdir(exist_ok=True)

    def get_or_create_machine_keys(self, machine_passport_id: str) -> tuple:
        """
        Get existing Ed25519 keypair for a machine, or generate a new one.
        Returns (signing_key_hex, verify_key_hex).
        """
        key_file = self.KEY_DIR / f"{machine_passport_id}.key"
        if key_file.exists():
            data = json.loads(key_file.read_text())
            return data["sk"], data["vk"]

        sk_hex, vk_hex = _generate_keypair()
        key_file.write_text(json.dumps({"sk": sk_hex, "vk": vk_hex}, indent=2))
        return sk_hex, vk_hex

    def sign_payload(self, message: bytes, signing_key_hex: str) -> str:
        """Sign a message with an Ed25519 signing key."""
        try:
            sk_bytes = bytes.fromhex(signing_key_hex)
            vk_bytes = bytes.fromhex(signing_key_hex)  # derive vk from sk
        except Exception:
            raise ValueError("Invalid signing key hex")

        if HAS_NACL:
            sk = SigningKey(sk_bytes, encoder=RawEncoder)
            signed = sk.sign(message, encoder=RawEncoder)
            return signed.signature.hex()
        elif HAS_ED25519:
            sk = ed25519.SigningKey(sk_bytes)
            sig = sk.sign(message)
            return sig.hex()
        else:
            raise RuntimeError("No Ed25519 library available. Install pynacl or ed25519.")

    def create_receipt(
        self,
        machine_passport_id: str,
        machine_model: str,
        session_id: str,
        renter: str,
        slot_hours: int,
        start_time: float,
        end_time: float,
        output_hash: str,
        attestation_proof: str,
    ) -> ProvenanceReceipt:
        """Create and sign a new provenance receipt."""
        import uuid
        receipt_id = f"receipt_{uuid.uuid4().hex[:16]}"

        sk_hex, vk_hex = self.get_or_create_machine_keys(machine_passport_id)

        # Build receipt (unsigned)
        receipt = ProvenanceReceipt(
            receipt_id=receipt_id,
            machine_passport_id=machine_passport_id,
            machine_model=machine_model,
            session_id=session_id,
            renter=renter,
            slot_hours=slot_hours,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=int(end_time - start_time),
            output_hash=output_hash,
            attestation_proof=attestation_proof,
            ed25519_pubkey=vk_hex,
            signature="",  # Will be filled below
        )

        # Sign the canonical payload
        canonical = receipt._canonical_json()
        sig_hex = self.sign_payload(canonical, sk_hex)
        receipt.signature = sig_hex

        # Persist
        self._save_receipt(receipt)
        return receipt

    def _save_receipt(self, receipt: ProvenanceReceipt):
        path = self.RECEIPTS_DIR / f"{receipt.receipt_id}.json"
        path.write_text(receipt.to_json())

    def get_receipt(self, receipt_id: str) -> Optional[ProvenanceReceipt]:
        path = self.RECEIPTS_DIR / f"{receipt_id}.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        return ProvenanceReceipt(**d)

    def list_receipts(self, renter: Optional[str] = None) -> List[ProvenanceReceipt]:
        receipts = []
        for path in self.RECEIPTS_DIR.glob("*.json"):
            d = json.loads(path.read_text())
            if renter is None or d.get("renter") == renter:
                receipts.append(ProvenanceReceipt(**d))
        return sorted(receipts, key=lambda r: r.signed_at, reverse=True)


if __name__ == "__main__":
    manager = ProvenanceReceiptManager()
    receipt = manager.create_receipt(
        machine_passport_id="old_ironsides",
        machine_model="IBM POWER8 8247-21L",
        session_id="sess_abc123xyz",
        renter="C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
        slot_hours=1,
        start_time=time.time(),
        end_time=time.time() + 3600,
        output_hash=hashlib.sha256(b"simulation_output_data").hexdigest(),
        attestation_proof="cpu_measurement_cycles=12345678,instruction_count=999999",
    )
    print(f"Receipt created: {receipt.receipt_id}")
    print(f"Signature: {receipt.signature[:32]}...")
    print(f"Verified: {receipt.verify()}")
    print(receipt.to_json())
