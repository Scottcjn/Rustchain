#!/usr/bin/env python3
"""Tests for Silicon Obituary Generator."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from silicon_obituary import EulogyGenerator, VideoCreator


class TestEulogyGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = EulogyGenerator()
        self.sample_miner = {
            "miner_id": "dual-g4-125",
            "wallet_address": "0x1234abcd",
            "architecture": "Power Mac G4",
            "multiplier": 2.5,
            "first_attestation": "2025-01-15T10:00:00",
            "last_attestation": "2026-07-10T08:00:00",
            "total_epochs": 847,
            "total_rtc": 412.0,
        }

    def test_generate_contains_real_data(self):
        eulogy = self.generator.generate(self.sample_miner)
        self.assertIn("dual-g4-125", eulogy)
        self.assertIn("Power Mac G4", eulogy)
        self.assertIn("847", eulogy)
        self.assertIn("412", eulogy)

    def test_generate_variety(self):
        eulogies = set()
        for _ in range(20):
            eulogy = self.generator.generate(self.sample_miner)
            eulogies.add(eulogy)
        self.assertGreater(len(eulogies), 1)

    def test_unknown_architecture(self):
        miner = dict(self.sample_miner)
        miner["architecture"] = "Quantum Flux Capacitor"
        eulogy = self.generator.generate(miner)
        self.assertIn("Quantum Flux Capacitor", eulogy)


class TestVideoCreator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.creator = VideoCreator(output_dir=self.temp_dir)

    def test_create_video_generates_files(self):
        miner = {"miner_id": "test-miner", "wallet_address": "0xabc", "architecture": "Raspberry Pi"}
        metadata = self.creator.create_video(miner, "Test eulogy")
        meta_file = Path(self.temp_dir) / "obituary_test-miner.json"
        self.assertTrue(meta_file.exists())
        with open(meta_file) as f:
            data = json.load(f)
        self.assertEqual(data["miner_id"], "test-miner")
        self.assertIn("#SiliconObituary", data["tags"])


if __name__ == "__main__":
    unittest.main()
