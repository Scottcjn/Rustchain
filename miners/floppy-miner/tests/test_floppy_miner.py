#!/usr/bin/env python3
"""
Tests for RustChain Floppy Miner

Run:
    python -m pytest miners/floppy-miner/tests/test_floppy_miner.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from floppy_miner import (
    BOOT_MEDIA,
    DEVICE_ARCH,
    DEVICE_FAMILY,
    FLOPPY_SIZE,
    MAX_RAM_MB,
    attestation_to_bytes,
    build_attestation,
    generate_hardware_fingerprint,
    generate_nonce,
    progress_bar,
    simulate_attestation,
)
from build_floppy import (
    SECTOR_SIZE,
    create_autoexec,
    create_boot_sector,
    create_config_sys,
    create_dir_entry,
    create_fat12,
)


# ── Fingerprint tests ────────────────────────────────────────────

class TestHardwareFingerprint(unittest.TestCase):
    def test_fingerprint_structure(self):
        fp = generate_hardware_fingerprint()
        self.assertIn("cpu_id", fp)
        self.assertIn("arch", fp)
        self.assertIn("family", fp)
        self.assertIn("ram_mb", fp)
        self.assertIn("boot_media", fp)

    def test_arch_is_i486(self):
        fp = generate_hardware_fingerprint()
        self.assertEqual(fp["arch"], "i486")

    def test_ram_under_16mb(self):
        fp = generate_hardware_fingerprint()
        self.assertLessEqual(fp["ram_mb"], 16)

    def test_boot_media_is_floppy(self):
        fp = generate_hardware_fingerprint()
        self.assertEqual(fp["boot_media"], "floppy_1.44mb")

    def test_unique_cpu_ids(self):
        fp1 = generate_hardware_fingerprint()
        fp2 = generate_hardware_fingerprint()
        # Should be unique (includes timestamp/pid)
        self.assertNotEqual(fp1["cpu_id"], fp2["cpu_id"])


# ── Nonce tests ──────────────────────────────────────────────────

class TestNonce(unittest.TestCase):
    def test_nonce_is_integer(self):
        n = generate_nonce()
        self.assertIsInstance(n, int)

    def test_nonce_is_positive(self):
        n = generate_nonce()
        self.assertGreater(n, 0)

    def test_nonce_fits_32bit(self):
        for _ in range(100):
            n = generate_nonce()
            self.assertLess(n, 2**31)

    def test_nonces_vary(self):
        nonces = {generate_nonce() for _ in range(10)}
        self.assertGreater(len(nonces), 1)


# ── Attestation payload tests ────────────────────────────────────

class TestAttestation(unittest.TestCase):
    def setUp(self):
        self.wallet = "RTCtest123"
        self.fp = generate_hardware_fingerprint()
        self.nonce = generate_nonce()

    def test_payload_has_required_fields(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        self.assertEqual(p["miner"], self.wallet)
        self.assertEqual(p["nonce"], self.nonce)
        self.assertIn("device", p)
        self.assertIn("timestamp", p)

    def test_device_has_arch(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        self.assertEqual(p["device"]["arch"], "i486")

    def test_device_has_family(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        self.assertEqual(p["device"]["family"], "floppy")

    def test_serialization_is_compact(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        data = attestation_to_bytes(p)
        # Should be < 512 bytes for single-packet transmission
        self.assertLess(len(data), 512)

    def test_serialization_is_valid_json(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        data = attestation_to_bytes(p)
        parsed = json.loads(data)
        self.assertEqual(parsed["miner"], self.wallet)

    def test_serialization_is_ascii(self):
        p = build_attestation(self.wallet, self.nonce, self.fp)
        data = attestation_to_bytes(p)
        data.decode("ascii")  # Should not raise


# ── Simulation tests ─────────────────────────────────────────────

class TestSimulation(unittest.TestCase):
    def test_simulate_returns_ok(self):
        result = simulate_attestation("RTCtest")
        self.assertTrue(result["ok"])

    def test_simulate_has_epoch(self):
        result = simulate_attestation("RTCtest")
        self.assertIn("epoch", result)

    def test_simulate_has_multiplier(self):
        result = simulate_attestation("RTCtest")
        self.assertEqual(result["multiplier"], 1.5)


# ── Progress bar tests ───────────────────────────────────────────

class TestProgressBar(unittest.TestCase):
    def test_zero_progress(self):
        bar = progress_bar(0, 10)
        self.assertIn("0%", bar)

    def test_full_progress(self):
        bar = progress_bar(10, 10)
        self.assertIn("100%", bar)

    def test_partial_progress(self):
        bar = progress_bar(5, 10)
        self.assertIn("50%", bar)


# ── Floppy image builder tests ───────────────────────────────────

class TestFloppyBuilder(unittest.TestCase):
    def test_boot_sector_size(self):
        boot = create_boot_sector()
        self.assertEqual(len(boot), 512)

    def test_boot_sector_signature(self):
        boot = create_boot_sector()
        self.assertEqual(boot[510], 0x55)
        self.assertEqual(boot[511], 0xAA)

    def test_boot_sector_oem(self):
        boot = create_boot_sector()
        self.assertEqual(boot[3:11], b'RUSTCHN ')

    def test_fat12_size(self):
        fat = create_fat12()
        self.assertEqual(len(fat), 9 * 512)

    def test_fat12_media_descriptor(self):
        fat = create_fat12()
        self.assertEqual(fat[0], 0xF0)  # 1.44MB floppy

    def test_dir_entry_size(self):
        entry = create_dir_entry("TEST", "TXT", 100, 2)
        self.assertEqual(len(entry), 32)

    def test_dir_entry_name(self):
        entry = create_dir_entry("MINER", "COM", 1024, 4)
        self.assertEqual(entry[0:8], b'MINER   ')
        self.assertEqual(entry[8:11], b'COM')

    def test_autoexec_content(self):
        bat = create_autoexec("RTCtest")
        self.assertIn(b"MINER.COM", bat)
        self.assertIn(b"RTCtest", bat)

    def test_config_sys(self):
        cfg = create_config_sys()
        self.assertIn(b"DOS=HIGH", cfg)
        self.assertIn(b"FILES=20", cfg)


# ── Memory constraint tests ──────────────────────────────────────

class TestConstraints(unittest.TestCase):
    def test_max_ram_is_16mb(self):
        self.assertEqual(MAX_RAM_MB, 16)

    def test_floppy_size_is_144(self):
        self.assertEqual(FLOPPY_SIZE, 1_474_560)

    def test_device_arch_is_i486(self):
        self.assertEqual(DEVICE_ARCH, "i486")

    def test_device_family_is_floppy(self):
        self.assertEqual(DEVICE_FAMILY, "floppy")

    def test_boot_media_constant(self):
        self.assertEqual(BOOT_MEDIA, "floppy_1.44mb")

    def test_total_code_fits_on_floppy(self):
        """All source files together must fit on 1.44MB."""
        total = 0
        base = os.path.join(os.path.dirname(__file__), "..")
        for root, dirs, files in os.walk(base):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        self.assertLess(total, FLOPPY_SIZE, "All source must fit on a floppy")


if __name__ == "__main__":
    unittest.main()
