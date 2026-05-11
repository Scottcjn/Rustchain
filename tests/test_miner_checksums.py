import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKSUMS = ROOT / "miners" / "checksums.sha256"


def test_miner_checksum_manifest_matches_committed_files():
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue

        expected_hash, relative_path = line.split(maxsplit=1)
        artifact = ROOT / "miners" / relative_path

        assert artifact.exists(), f"checksum entry points at missing file: {relative_path}"
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"stale checksum for {relative_path}"
