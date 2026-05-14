# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rom_fingerprint_db.py"

spec = importlib.util.spec_from_file_location("rom_fingerprint_db", MODULE_PATH)
rom_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rom_db)


def test_identify_rom_is_case_insensitive_for_known_amiga_sha1():
    info = rom_db.identify_rom("891E9A547772FE0C6C19B610BAF8BC4EA7FCB785", "sha1")

    assert info is not None
    assert info["platform"] == "amiga"
    assert info["hash_type"] == "sha1"
    assert "A500" in info["models"]


def test_identify_rom_supports_apple_checksum_case_insensitive():
    info = rom_db.identify_rom("28ba61ce", "apple")

    assert info is not None
    assert info["platform"] == "mac_68k"
    assert info["hash_type"] == "apple_checksum"
    assert info["models"] == ["Mac 128K"]


def test_compute_file_hash_missing_file_returns_none(tmp_path):
    assert rom_db.compute_file_hash(str(tmp_path / "missing.rom"), "sha1") is None


def test_compute_file_hash_reads_file_in_chunks(tmp_path):
    rom_path = tmp_path / "sample.rom"
    rom_path.write_bytes(b"abc")

    assert rom_db.compute_file_hash(str(rom_path), "sha1") == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert rom_db.compute_file_hash(str(rom_path), "md5") == "900150983cd24fb0d6963f7d28e17f72"


def test_rom_cluster_detector_allows_duplicate_same_miner():
    detector = rom_db.ROMClusterDetector(cluster_threshold=1)

    assert detector.report_rom("miner-a", "unique_hash") == (True, "unique_rom")
    assert detector.report_rom("miner-a", "unique_hash") == (True, "same_miner_update")
    assert detector.get_clusters() == {}


def test_rom_cluster_detector_flags_second_unique_miner_when_threshold_exceeded():
    detector = rom_db.ROMClusterDetector(cluster_threshold=1)

    assert detector.report_rom("miner-a", "unique_hash") == (True, "unique_rom")
    ok, reason = detector.report_rom("miner-b", "unique_hash")

    assert ok is False
    assert reason == "rom_clustering_detected:shared_with:['miner-a']"
    assert detector.get_clusters() == {"sha1:unique_hash": ["miner-a", "miner-b"]}
    assert set(detector.get_suspicious_miners()) == {"miner-a", "miner-b"}


def test_rom_cluster_detector_rejects_known_emulator_rom_immediately():
    detector = rom_db.ROMClusterDetector(cluster_threshold=99)

    ok, reason = detector.report_rom("miner-a", "891e9a547772fe0c6c19b610baf8bc4ea7fcb785")

    assert ok is False
    assert reason.startswith("known_emulator_rom:amiga:")
