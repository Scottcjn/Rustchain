# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Floppy Witness Kit (Bounty #2313)."""

import json
import os
import struct
import tempfile
import pytest
from pathlib import Path

from witness_format import (
    EpochWitness,
    MinerEntry,
    write_witnesses_to_image,
    read_witnesses_from_image,
    verify_witness,
    witnesses_per_disk,
    WITNESS_MAGIC,
    FLOPPY_SIZE,
    ZIP_DISK_SIZE,
    MAX_WITNESS_SIZE,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_witness():
    return EpochWitness(
        epoch=500,
        timestamp=1711324800,
        settlement_hash="a1b2c3d4e5f6" + "0" * 52,
        ergo_anchor_txid="f6e5d4c3b2a1" + "0" * 52,
        commitment_hash="1234567890ab" + "0" * 52,
        merkle_proof=["ab" * 32, "cd" * 32],
        miners=[
            MinerEntry("miner-alpha", "G4", 2.5),
            MinerEntry("miner-beta", "SPARC", 3.0),
            MinerEntry("miner-gamma", "G5", 2.5),
        ],
        total_rtc_distributed=75.5,
        node_count=4,
    )


@pytest.fixture
def sample_miner():
    return MinerEntry("test-miner-001", "G4", 2.5)


@pytest.fixture
def tmp_image(tmp_path):
    return str(tmp_path / "test.img")


# ── MinerEntry Tests ──────────────────────────────────────────────

class TestMinerEntry:
    def test_create(self, sample_miner):
        assert sample_miner.miner_id == "test-miner-001"
        assert sample_miner.architecture == "G4"
        assert sample_miner.multiplier == 2.5

    def test_compact_roundtrip(self, sample_miner):
        data = sample_miner.to_compact()
        assert len(data) == 28  # Fixed size
        restored = MinerEntry.from_compact(data)
        assert restored.miner_id == sample_miner.miner_id
        assert restored.architecture == sample_miner.architecture
        assert abs(restored.multiplier - sample_miner.multiplier) < 0.01

    def test_long_id_truncated(self):
        m = MinerEntry("a" * 50, "POWERPC", 1.0)
        data = m.to_compact()
        restored = MinerEntry.from_compact(data)
        assert len(restored.miner_id) <= 16


# ── EpochWitness Tests ────────────────────────────────────────────

class TestEpochWitness:
    def test_create(self, sample_witness):
        assert sample_witness.epoch == 500
        assert len(sample_witness.miners) == 3

    def test_witness_hash_deterministic(self, sample_witness):
        h1 = sample_witness.compute_witness_hash()
        h2 = sample_witness.compute_witness_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_witness_hash_changes(self, sample_witness):
        h1 = sample_witness.compute_witness_hash()
        sample_witness.epoch = 501
        h2 = sample_witness.compute_witness_hash()
        assert h1 != h2

    def test_json_roundtrip(self, sample_witness):
        j = sample_witness.to_json()
        restored = EpochWitness.from_json(j)
        assert restored.epoch == 500
        assert len(restored.miners) == 3
        assert restored.miners[0].miner_id == "miner-alpha"

    def test_compact_roundtrip(self, sample_witness):
        data = sample_witness.to_compact()
        restored = EpochWitness.from_compact(data)
        assert restored.epoch == 500
        assert restored.timestamp == 1711324800
        assert len(restored.miners) == 3
        assert restored.miners[1].architecture == "SPARC"

    def test_compact_size_under_limit(self, sample_witness):
        data = sample_witness.to_compact()
        assert len(data) < MAX_WITNESS_SIZE

    def test_to_dict(self, sample_witness):
        d = sample_witness.to_dict()
        assert d["epoch"] == 500
        assert isinstance(d["miners"], list)

    def test_invalid_magic_rejected(self):
        """Compact data with wrong magic bytes should be rejected."""
        import zlib as _zlib
        # Build valid-looking compressed data but with wrong magic inside
        bad_payload = b"BAD!" + b"\x01" + b"\x00" * 200
        compressed = _zlib.compress(bad_payload, 9)
        data = struct.pack(">I", len(compressed)) + compressed
        with pytest.raises(ValueError, match="Invalid witness magic"):
            EpochWitness.from_compact(data)


# ── Disk Image Tests ──────────────────────────────────────────────

class TestDiskImage:
    def test_write_and_read_floppy(self, sample_witness, tmp_image):
        ok, msg = write_witnesses_to_image([sample_witness], tmp_image)
        assert ok is True
        assert Path(tmp_image).exists()
        assert Path(tmp_image).stat().st_size == FLOPPY_SIZE

        witnesses = read_witnesses_from_image(tmp_image)
        assert len(witnesses) == 1
        assert witnesses[0].epoch == 500

    def test_multiple_witnesses(self, tmp_image):
        witnesses = []
        for i in range(100):
            w = EpochWitness(
                epoch=i + 1,
                timestamp=1711324800 + i * 60,
                settlement_hash=f"{i:064x}",
                ergo_anchor_txid=f"{i+1000:064x}",
                commitment_hash=f"{i+2000:064x}",
                miners=[MinerEntry(f"miner-{i}", "G4", 2.5)],
                total_rtc_distributed=10.0,
            )
            witnesses.append(w)

        ok, msg = write_witnesses_to_image(witnesses, tmp_image)
        assert ok is True

        restored = read_witnesses_from_image(tmp_image)
        assert len(restored) == 100
        assert restored[0].epoch == 1
        assert restored[99].epoch == 100

    def test_empty_witnesses_rejected(self, tmp_image):
        ok, msg = write_witnesses_to_image([], tmp_image)
        assert ok is False

    def test_invalid_image_rejected(self, tmp_path):
        bad_file = tmp_path / "bad.img"
        bad_file.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError):
            read_witnesses_from_image(str(bad_file))

    def test_fits_on_floppy(self, tmp_image):
        """1000 witnesses should fit on a 1.44MB floppy."""
        witnesses = [
            EpochWitness(
                epoch=i,
                timestamp=1711324800 + i,
                settlement_hash=f"{i:064x}",
                ergo_anchor_txid=f"{i:064x}",
                commitment_hash=f"{i:064x}",
                miners=[MinerEntry(f"m{i}", "G4", 2.5)],
            )
            for i in range(1, 1001)
        ]
        ok, msg = write_witnesses_to_image(witnesses, tmp_image, FLOPPY_SIZE)
        assert ok is True


# ── Verification Tests ────────────────────────────────────────────

class TestVerification:
    def test_valid_witness(self, sample_witness):
        ok, msg = verify_witness(sample_witness)
        assert ok is True
        assert "VALID" in msg

    def test_empty_settlement_hash(self):
        w = EpochWitness(epoch=1, timestamp=1000, settlement_hash="0" * 64)
        ok, msg = verify_witness(w)
        assert ok is False
        assert "Empty" in msg

    def test_zero_epoch(self):
        w = EpochWitness(epoch=0, timestamp=1000, settlement_hash="a" * 64)
        ok, msg = verify_witness(w)
        assert ok is False

    def test_zero_timestamp(self):
        w = EpochWitness(epoch=1, timestamp=0, settlement_hash="a" * 64)
        ok, msg = verify_witness(w)
        assert ok is False


# ── Capacity Tests ────────────────────────────────────────────────

class TestCapacity:
    def test_floppy_capacity(self):
        cap = witnesses_per_disk(FLOPPY_SIZE)
        assert cap > 1000  # Should hold at least 1000 witnesses

    def test_zip_disk_capacity(self):
        cap = witnesses_per_disk(ZIP_DISK_SIZE)
        assert cap > 10000  # ZIP holds way more than floppy
        assert witnesses_per_disk(ZIP_DISK_SIZE) > witnesses_per_disk(FLOPPY_SIZE)


# ── Helpers ───────────────────────────────────────────────────────

def zlib_compress_dummy():
    """Create a dummy compressed payload that will fail magic check."""
    import zlib
    return struct.pack(">I", 10) + zlib.compress(b"BAD_MAGIC\x01" + b"\x00" * 200)
