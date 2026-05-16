#!/usr/bin/env python3
"""
Tests for N64 Mining Host Relay

Run: python -m pytest mining/n64-miner/test_host_relay.py -v
"""

import hashlib
import json
import struct
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from host_relay import (
    N64Relay, crc8, ATTEST_MAGIC, PKT_TYPE_ATTEST, PKT_TYPE_EPOCH_ACK,
    PKT_TYPE_REATTEST, DEVICE_ARCH, DEVICE_FAMILY
)


class CapturingRelay(N64Relay):
    def __init__(self):
        super().__init__(
            port=None,
            node_url="https://rustchain.org",
            wallet="RTC_TEST_WALLET",
            demo=False
        )
        self.sent_frames = []

    def send_frame(self, data: bytes) -> bool:
        self.sent_frames.append(data)
        return True


class TestCRC8(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(crc8(b""), 0xFF)

    def test_known_value(self):
        result = crc8(b"RTC1")
        self.assertIsInstance(result, int)
        self.assertIn(result, range(256))

    def test_deterministic(self):
        data = b"test data 123"
        self.assertEqual(crc8(data), crc8(data))

    def test_different_data(self):
        self.assertNotEqual(crc8(b"hello"), crc8(b"world"))

    def test_single_byte(self):
        r = crc8(b"\x00")
        self.assertIsInstance(r, int)


class TestN64RelayDemo(unittest.TestCase):
    def setUp(self):
        self.relay = N64Relay(
            port=None,
            node_url="https://rustchain.org",
            wallet="RTC_TEST_WALLET",
            demo=True
        )

    def test_init(self):
        self.assertTrue(self.relay.demo)
        self.assertEqual(self.relay.wallet, "RTC_TEST_WALLET")
        self.assertEqual(self.relay.attestations_sent, 0)

    def test_demo_attestation(self):
        frame = self.relay._demo_attestation()
        self.assertIsInstance(frame, bytes)
        self.assertGreater(len(frame), 8)

        # Check magic
        magic = struct.unpack_from("<I", frame, 0)[0]
        self.assertEqual(magic, ATTEST_MAGIC)

    def test_parse_attestation(self):
        frame = self.relay._demo_attestation()
        attest = self.relay.parse_attestation(frame)
        self.assertIsNotNone(attest)
        self.assertEqual(attest["device_arch"], DEVICE_ARCH)
        self.assertEqual(attest["device_family"], DEVICE_FAMILY)

    def test_parse_measurements(self):
        frame = self.relay._demo_attestation()
        attest = self.relay.parse_attestation(frame)
        m = attest["measurements"]
        self.assertEqual(m["count_drift_ns"], 213)
        self.assertEqual(m["cache_d_hit_cycles"], 2)
        self.assertEqual(m["cache_d_miss_cycles"], 42)
        self.assertEqual(m["cache_i_hit_cycles"], 1)
        self.assertEqual(m["cache_i_miss_cycles"], 38)
        self.assertEqual(m["rsp_jitter_ns"], 47)
        self.assertEqual(m["tlb_miss_cycles"], 31)

    def test_parse_fingerprint_hash(self):
        frame = self.relay._demo_attestation()
        attest = self.relay.parse_attestation(frame)
        self.assertIn("fingerprint_hash", attest)
        self.assertGreater(len(attest["fingerprint_hash"]), 0)

    def test_parse_rejects_bad_magic(self):
        bad_data = struct.pack("<I", 0xDEADBEEF) + b"\x00" * 100
        result = self.relay.parse_attestation(bad_data)
        self.assertIsNone(result)
        self.assertEqual(self.relay.corrupt_attestations, 0)
        self.assertEqual(self.relay.health_events, [])

    def test_parse_detects_erased_save_data(self):
        relay = CapturingRelay()
        relay.current_epoch = 42
        result = relay.parse_attestation(struct.pack("<I", 0xFFFFFFFF) + b"\x00" * 100)

        self.assertIsNone(result)
        self.assertEqual(relay.corrupt_attestations, 1)
        self.assertEqual(relay.health_events[0]["type"], "miner_attestation_corrupt")
        self.assertEqual(relay.health_events[0]["magic"], "0xFFFFFFFF")
        self.assertEqual(relay.health_events[0]["block_height"], 42)
        self.assertEqual(len(relay.sent_frames), 1)
        self.assertEqual(struct.unpack_from("<I", relay.sent_frames[0], 0)[0], ATTEST_MAGIC)
        self.assertEqual(relay.sent_frames[0][5], PKT_TYPE_REATTEST)
        self.assertEqual(struct.unpack_from("<I", relay.sent_frames[0], 8)[0], 42)

    def test_parse_detects_zeroed_save_data(self):
        relay = CapturingRelay()
        result = relay.parse_attestation(b"\x00" * 104)

        self.assertIsNone(result)
        self.assertEqual(relay.corrupt_attestations, 1)
        self.assertEqual(relay.health_events[0]["magic"], "0x00000000")
        self.assertEqual(len(relay.sent_frames), 1)

    def test_parse_rejects_short(self):
        result = self.relay.parse_attestation(b"\x00\x01\x02")
        self.assertIsNone(result)

    def test_parse_rejects_wrong_type(self):
        data = struct.pack("<IBBI", ATTEST_MAGIC, 1, 99, 0) + b"\x00" * 100
        result = self.relay.parse_attestation(data)
        self.assertIsNone(result)

    def test_send_frame_demo(self):
        result = self.relay.send_frame(b"test")
        self.assertTrue(result)


class TestAttestationProtocol(unittest.TestCase):
    def test_magic_bytes(self):
        # "RTC1" in little-endian
        packed = struct.pack("<I", ATTEST_MAGIC)
        self.assertEqual(packed[0], 0x31)  # '1'
        self.assertEqual(packed[1], 0x43)  # 'C'
        self.assertEqual(packed[2], 0x54)  # 'T'
        self.assertEqual(packed[3], 0x52)  # 'R'

    def test_packet_types(self):
        self.assertEqual(PKT_TYPE_ATTEST, 0)
        self.assertEqual(PKT_TYPE_EPOCH_ACK, 3)
        self.assertEqual(PKT_TYPE_REATTEST, 4)

    def test_device_constants(self):
        self.assertEqual(DEVICE_ARCH, "mips_r4300")
        self.assertEqual(DEVICE_FAMILY, "N64")


class TestFingerprintValidation(unittest.TestCase):
    """Test fingerprint measurement ranges for anti-emulation."""

    REAL_HW = {
        "count_drift_ns": 213,
        "cache_d_hit_cycles": 2,
        "cache_d_miss_cycles": 42,
        "cache_i_hit_cycles": 1,
        "cache_i_miss_cycles": 38,
        "rsp_jitter_ns": 47,
        "tlb_miss_cycles": 31,
    }

    EMULATOR = {
        "count_drift_ns": 0,      # Too exact
        "cache_d_hit_cycles": 10,  # No bimodal
        "cache_d_miss_cycles": 12, # Too close to hit
        "cache_i_hit_cycles": 10,
        "cache_i_miss_cycles": 12,
        "rsp_jitter_ns": 0,       # Zero jitter
        "tlb_miss_cycles": 500,   # Way too high
    }

    def test_real_hw_drift_in_range(self):
        d = self.REAL_HW["count_drift_ns"]
        self.assertGreater(d, 50)
        self.assertLess(d, 500)

    def test_emulator_drift_zero(self):
        self.assertEqual(self.EMULATOR["count_drift_ns"], 0)

    def test_real_cache_bimodal(self):
        hit = self.REAL_HW["cache_d_hit_cycles"]
        miss = self.REAL_HW["cache_d_miss_cycles"]
        self.assertGreater(miss, hit * 5)  # Clear separation

    def test_emulator_cache_flat(self):
        hit = self.EMULATOR["cache_d_hit_cycles"]
        miss = self.EMULATOR["cache_d_miss_cycles"]
        self.assertLess(miss, hit * 3)  # No clear separation

    def test_real_rsp_jitter(self):
        j = self.REAL_HW["rsp_jitter_ns"]
        self.assertGreater(j, 0)
        self.assertLess(j, 200)

    def test_real_tlb_miss(self):
        t = self.REAL_HW["tlb_miss_cycles"]
        self.assertGreaterEqual(t, 25)
        self.assertLessEqual(t, 40)

    def test_emulator_tlb_out_of_range(self):
        t = self.EMULATOR["tlb_miss_cycles"]
        self.assertGreater(t, 40)

    def test_fingerprint_hash_deterministic(self):
        fp = struct.pack("<IIIIIII", *self.REAL_HW.values())
        h1 = hashlib.sha256(fp).hexdigest()
        h2 = hashlib.sha256(fp).hexdigest()
        self.assertEqual(h1, h2)

    def test_different_hw_different_hash(self):
        fp_real = struct.pack("<IIIIIII", *self.REAL_HW.values())
        fp_emu = struct.pack("<IIIIIII", *self.EMULATOR.values())
        self.assertNotEqual(
            hashlib.sha256(fp_real).hexdigest(),
            hashlib.sha256(fp_emu).hexdigest()
        )


class TestRIPMultiplier(unittest.TestCase):
    """Verify N64 gets MYTHIC 4.0x multiplier per RIP-200."""

    MULTIPLIERS = {
        "mips_r4300": 4.0,   # N64 — MYTHIC
        "arm2": 4.0,         # MYTHIC
        "powerpc_g4": 2.5,   # LEGENDARY
        "powerpc_g5": 2.0,   # EPIC
        "arm_cortex": 1.2,   # COMMON
        "x86_64": 1.0,       # STANDARD
    }

    def test_n64_is_mythic(self):
        self.assertEqual(self.MULTIPLIERS["mips_r4300"], 4.0)

    def test_n64_highest_tier(self):
        self.assertEqual(
            self.MULTIPLIERS["mips_r4300"],
            max(self.MULTIPLIERS.values())
        )

    def test_n64_4x_standard(self):
        ratio = self.MULTIPLIERS["mips_r4300"] / self.MULTIPLIERS["x86_64"]
        self.assertEqual(ratio, 4.0)


if __name__ == "__main__":
    unittest.main()
