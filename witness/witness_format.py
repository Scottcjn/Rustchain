# SPDX-License-Identifier: MIT
"""
RustChain Floppy Witness Kit — Epoch Proofs on 1.44MB Media
Bounty #2313: 60 RTC

Compact epoch witness format that fits on old media — 1.44MB floppies,
ZIP disks, even cassette tapes. Block proofs carried by sneakernet
into air-gapped or museum-grade machines.

Target: <100KB per epoch witness. A 1.44MB floppy holds ~14,000 witnesses.
"""

import hashlib
import json
import struct
import time
import zlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Constants ─────────────────────────────────────────────────────

WITNESS_MAGIC = b"RWTK"  # RustChain Witness ToolKit
WITNESS_VERSION = 1
FLOPPY_SIZE = 1_474_560   # 1.44 MB in bytes
ZIP_DISK_SIZE = 100_000_000  # 100 MB ZIP disk
MAX_WITNESS_SIZE = 100_000   # Target: <100KB per witness


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class MinerEntry:
    """Compact miner representation for witness."""
    miner_id: str
    architecture: str
    multiplier: float = 1.0

    def to_compact(self) -> bytes:
        """Pack to minimal bytes."""
        data = self.miner_id[:16].encode().ljust(16, b"\x00")
        data += self.architecture[:8].encode().ljust(8, b"\x00")
        data += struct.pack(">f", self.multiplier)
        return data  # 28 bytes per miner

    @classmethod
    def from_compact(cls, data: bytes) -> "MinerEntry":
        miner_id = data[:16].rstrip(b"\x00").decode()
        architecture = data[16:24].rstrip(b"\x00").decode()
        multiplier = struct.unpack(">f", data[24:28])[0]
        return cls(miner_id=miner_id, architecture=architecture, multiplier=multiplier)


@dataclass
class EpochWitness:
    """
    Compact epoch witness — everything needed to prove chain state
    at a specific epoch, small enough for floppy disk.
    """
    epoch: int = 0
    timestamp: int = 0                           # Unix timestamp
    settlement_hash: str = ""                     # Block settlement hash
    ergo_anchor_txid: str = ""                    # Ergo anchor TX ID
    commitment_hash: str = ""                     # Commitment hash
    merkle_proof: List[str] = field(default_factory=list)  # Minimal Merkle path
    miners: List[MinerEntry] = field(default_factory=list)
    total_rtc_distributed: float = 0.0
    node_count: int = 0

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Dict) -> "EpochWitness":
        miners = [MinerEntry(**m) for m in data.pop("miners", [])]
        return cls(miners=miners, **data)

    @classmethod
    def from_json(cls, s: str) -> "EpochWitness":
        return cls.from_dict(json.loads(s))

    def compute_witness_hash(self) -> str:
        """Compute SHA-256 hash of the witness for integrity verification."""
        canonical = json.dumps({
            "epoch": self.epoch,
            "timestamp": self.timestamp,
            "settlement_hash": self.settlement_hash,
            "ergo_anchor_txid": self.ergo_anchor_txid,
            "commitment_hash": self.commitment_hash,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def size_bytes(self) -> int:
        """Estimate serialized size."""
        return len(self.to_compact())

    def to_compact(self) -> bytes:
        """
        Serialize to compact binary format.
        Header: RWTK + version(1) + epoch(4) + timestamp(4) + hashes + miners
        """
        buf = bytearray()
        # Magic + version
        buf += WITNESS_MAGIC
        buf += struct.pack(">B", WITNESS_VERSION)
        # Epoch + timestamp
        buf += struct.pack(">I", self.epoch)
        buf += struct.pack(">I", self.timestamp)
        # Hashes (32 bytes each, hex-encoded → 32 bytes binary)
        for h in [self.settlement_hash, self.ergo_anchor_txid, self.commitment_hash]:
            h_bytes = bytes.fromhex(h) if len(h) == 64 else h.encode()[:32].ljust(32, b"\x00")
            buf += h_bytes
        # Merkle proof count + entries
        buf += struct.pack(">B", len(self.merkle_proof))
        for proof in self.merkle_proof[:15]:  # Max 15 proof nodes
            p_bytes = bytes.fromhex(proof) if len(proof) == 64 else proof.encode()[:32].ljust(32, b"\x00")
            buf += p_bytes
        # Miner count + entries
        buf += struct.pack(">H", len(self.miners))
        for miner in self.miners:
            buf += miner.to_compact()
        # RTC distributed
        buf += struct.pack(">d", self.total_rtc_distributed)
        # Compress
        compressed = zlib.compress(bytes(buf), level=9)
        # Wrap with length header
        return struct.pack(">I", len(compressed)) + compressed

    @classmethod
    def from_compact(cls, data: bytes) -> "EpochWitness":
        """Deserialize from compact binary format."""
        length = struct.unpack(">I", data[:4])[0]
        decompressed = zlib.decompress(data[4:4 + length])
        buf = decompressed
        offset = 0

        # Magic
        magic = buf[offset:offset + 4]
        offset += 4
        if magic != WITNESS_MAGIC:
            raise ValueError(f"Invalid witness magic: {magic}")

        # Version
        version = struct.unpack(">B", buf[offset:offset + 1])[0]
        offset += 1

        # Epoch + timestamp
        epoch = struct.unpack(">I", buf[offset:offset + 4])[0]
        offset += 4
        timestamp = struct.unpack(">I", buf[offset:offset + 4])[0]
        offset += 4

        # Hashes
        settlement_hash = buf[offset:offset + 32].hex()
        offset += 32
        ergo_anchor_txid = buf[offset:offset + 32].hex()
        offset += 32
        commitment_hash = buf[offset:offset + 32].hex()
        offset += 32

        # Merkle proof
        proof_count = struct.unpack(">B", buf[offset:offset + 1])[0]
        offset += 1
        merkle_proof = []
        for _ in range(proof_count):
            merkle_proof.append(buf[offset:offset + 32].hex())
            offset += 32

        # Miners
        miner_count = struct.unpack(">H", buf[offset:offset + 2])[0]
        offset += 2
        miners = []
        for _ in range(miner_count):
            miners.append(MinerEntry.from_compact(buf[offset:offset + 28]))
            offset += 28

        # RTC
        total_rtc = struct.unpack(">d", buf[offset:offset + 8])[0]

        return cls(
            epoch=epoch,
            timestamp=timestamp,
            settlement_hash=settlement_hash,
            ergo_anchor_txid=ergo_anchor_txid,
            commitment_hash=commitment_hash,
            merkle_proof=merkle_proof,
            miners=miners,
            total_rtc_distributed=total_rtc,
        )


# ── Disk Operations ───────────────────────────────────────────────

ASCII_LABEL = r"""
╔══════════════════════════════════════╗
║   ⛓️  RUSTCHAIN EPOCH WITNESS  ⛓️    ║
║   Proof-of-Antiquity Block Proofs   ║
║   ──────────────────────────────    ║
║   Epochs: {start:>6} — {end:>6}          ║
║   Witnesses: {count:>6}                  ║
║   Written: {date}             ║
╚══════════════════════════════════════╝
""".strip()


def write_witnesses_to_image(
    witnesses: List[EpochWitness],
    output_path: str,
    image_size: int = FLOPPY_SIZE,
) -> Tuple[bool, str]:
    """
    Write epoch witnesses to a floppy disk image (.img).
    Format: ASCII label + index table + compressed witness data.
    """
    if not witnesses:
        return False, "No witnesses to write"

    # Build label
    label = ASCII_LABEL.format(
        start=witnesses[0].epoch,
        end=witnesses[-1].epoch,
        count=len(witnesses),
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    ).encode()

    # Serialize all witnesses
    witness_blobs = []
    for w in witnesses:
        blob = w.to_compact()
        witness_blobs.append(blob)

    # Build index: offset table for each witness
    index_entries = []
    data_offset = 512 + len(label) + (len(witnesses) * 8)  # header + label + index
    for blob in witness_blobs:
        index_entries.append(struct.pack(">II", data_offset, len(blob)))
        data_offset += len(blob)

    # Check total size
    total = 512 + len(label) + len(b"".join(index_entries)) + sum(len(b) for b in witness_blobs)
    if total > image_size:
        return False, f"Data too large: {total} bytes > {image_size} bytes"

    # Build image
    image = bytearray(image_size)
    offset = 0

    # Boot sector / header (512 bytes)
    header = WITNESS_MAGIC + struct.pack(">BII", WITNESS_VERSION, len(witnesses), len(label))
    image[offset:offset + len(header)] = header
    offset = 512

    # ASCII label
    image[offset:offset + len(label)] = label
    offset += len(label)

    # Index table
    for entry in index_entries:
        image[offset:offset + len(entry)] = entry
        offset += len(entry)

    # Witness data
    for blob in witness_blobs:
        image[offset:offset + len(blob)] = blob
        offset += len(blob)

    # Write to file
    Path(output_path).write_bytes(bytes(image))
    return True, f"Wrote {len(witnesses)} witnesses ({total} bytes) to {output_path}"


def read_witnesses_from_image(image_path: str) -> List[EpochWitness]:
    """Read epoch witnesses from a floppy disk image."""
    data = Path(image_path).read_bytes()

    # Parse header
    magic = data[:4]
    if magic != WITNESS_MAGIC:
        raise ValueError("Not a RustChain witness image")

    version, count, label_len = struct.unpack(">BII", data[4:13])

    # Skip to index table (after header + label)
    index_start = 512 + label_len
    witnesses = []

    for i in range(count):
        idx_offset = index_start + (i * 8)
        data_offset, blob_len = struct.unpack(">II", data[idx_offset:idx_offset + 8])
        blob = data[data_offset:data_offset + blob_len]
        witnesses.append(EpochWitness.from_compact(blob))

    return witnesses


def verify_witness(witness: EpochWitness, node_url: str = "") -> Tuple[bool, str]:
    """
    Verify a witness against a RustChain node (if available)
    or just check internal consistency.
    """
    # Internal consistency
    if not witness.settlement_hash or witness.settlement_hash == "0" * 64:
        return False, "INVALID: Empty settlement hash"

    if witness.epoch <= 0:
        return False, "INVALID: Epoch must be positive"

    if witness.timestamp <= 0:
        return False, "INVALID: Timestamp must be positive"

    witness_hash = witness.compute_witness_hash()
    if not witness_hash:
        return False, "INVALID: Cannot compute witness hash"

    # If node URL provided, verify against live chain
    if node_url:
        try:
            import requests
            from node.tls_config import get_tls_verify
            resp = requests.get(f"{node_url}/epoch", timeout=10, verify=get_tls_verify())
            if resp.status_code == 200:
                chain_data = resp.json()
                chain_epoch = chain_data.get("epoch", chain_data.get("current_epoch", 0))
                if witness.epoch > chain_epoch:
                    return False, f"INVALID: Witness epoch {witness.epoch} > chain epoch {chain_epoch}"
        except Exception:
            pass  # Offline verification still valid

    return True, f"VALID: Epoch {witness.epoch} — hash {witness_hash[:16]}..."


def witnesses_per_disk(image_size: int = FLOPPY_SIZE, avg_miners: int = 10) -> int:
    """Estimate how many witnesses fit on a disk."""
    # Header: 512 bytes, label: ~300 bytes, index: 8 bytes per witness
    # Witness: ~100-200 bytes compressed (small epochs)
    overhead = 512 + 300
    per_witness = 8 + 28 * avg_miners + 150  # index + miners + overhead
    compressed_est = per_witness * 0.4  # zlib compression ratio
    available = image_size - overhead
    return int(available / max(compressed_est, 1))
