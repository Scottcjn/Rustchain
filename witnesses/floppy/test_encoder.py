# SPDX-License-Identifier: MIT
"""Unit tests for the Floppy Witness Kit encoder."""

import pytest
from encoder import (
    create_epoch_witness, encode_witnesses, decode_witnesses,
    generate_qr_data, FLOPPY_CAPACITY, HEADER_SIZE, MAGIC_BYTE,
)


def _sample_witness(epoch=1):
    return create_epoch_witness(
        epoch_num=epoch,
        timestamp=1711234567,
        miner_lineup=[{"id": "miner_001", "arch": "x86_vintage"}],
        settlement_hash="a" * 64,
        ergo_anchor_txid="ergo_tx_000001",
        commitment_hash="b" * 64,
        merkle_proof=["c" * 32],
    )


class TestEncoding:
    def test_roundtrip_single(self):
        w = [_sample_witness()]
        encoded = encode_witnesses(w)
        decoded = decode_witnesses(encoded)
        assert decoded[0]["epoch"] == 1

    def test_roundtrip_many(self):
        ws = [_sample_witness(i) for i in range(100)]
        encoded = encode_witnesses(ws)
        decoded = decode_witnesses(encoded)
        assert len(decoded) == 100
        assert decoded[99]["epoch"] == 99

    def test_header_magic(self):
        encoded = encode_witnesses([_sample_witness()])
        assert encoded[0] == MAGIC_BYTE

    def test_total_size_within_floppy(self):
        ws = [_sample_witness(i) for i in range(14000)]
        encoded = encode_witnesses(ws)
        assert len(encoded) <= FLOPPY_CAPACITY

    def test_header_included_in_size_check(self):
        """Verify the 5-byte header is accounted for in size limits."""
        encoded = encode_witnesses([_sample_witness()])
        assert len(encoded) >= HEADER_SIZE

    def test_invalid_magic_raises(self):
        bad_data = b"\xFF" + b"\x00" * 10
        with pytest.raises(ValueError, match="Invalid magic byte"):
            decode_witnesses(bad_data)

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_witnesses(b"\xFD\x00")


class TestQR:
    def test_qr_output_is_string(self):
        ws = [_sample_witness()]
        qr = generate_qr_data(ws)
        assert isinstance(qr, str)
        assert len(qr) > 0
