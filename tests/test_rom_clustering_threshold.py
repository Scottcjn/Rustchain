# SPDX-License-Identifier: MIT
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = REPO_ROOT / "node"
sys.path.insert(0, str(NODE_DIR))

from rom_clustering_server import ROMClusteringServer
from rom_fingerprint_db import ROMClusterDetector


def test_server_default_threshold_flags_second_unique_miner(tmp_path):
    server = ROMClusteringServer(str(tmp_path / "roms.db"))
    rom_hash = "12" * 20

    assert server.process_rom_report("miner-a", rom_hash)[1] == "unique_rom"
    assert server.process_rom_report("miner-b", rom_hash)[1] == "rom_clustering"


def test_detector_default_threshold_flags_second_unique_miner():
    detector = ROMClusterDetector()

    assert detector.report_rom("miner-a", "unique_rom_hash") == (True, "unique_rom")
    ok, reason = detector.report_rom("miner-b", "unique_rom_hash")

    assert ok is False
    assert reason == "rom_clustering_detected:shared_with:['miner-a']"
    assert set(detector.get_suspicious_miners()) == {"miner-a", "miner-b"}
