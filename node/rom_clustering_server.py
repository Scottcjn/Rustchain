#!/usr/bin/env python3
"""
ROM Clustering Detection - Server Side
=======================================
Integrates with RustChain server to detect emulated miners.

When multiple "different" miners report identical ROM hashes,
they're likely VMs using the same ROM pack - flag them.
"""

import sqlite3
import time
from typing import Dict, List, Optional, Tuple
from rom_fingerprint_db import (
    identify_rom,
    is_known_emulator_rom,
    AMIGA_KICKSTART_SHA1,
    MAC_68K_CHECKSUMS,
    MAC_PPC_MD5,
)

# =============================================================================
# DATABASE SCHEMA ADDITIONS
# =============================================================================
ROM_CLUSTERING_SCHEMA = """
-- ROM hash reports from miners
CREATE TABLE IF NOT EXISTS miner_rom_reports (
    miner_id TEXT NOT NULL,
    rom_hash TEXT NOT NULL,
    hash_type TEXT NOT NULL,  -- sha1, md5, apple
    platform TEXT,            -- amiga, mac_68k, mac_ppc
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    report_count INTEGER DEFAULT 1,
    PRIMARY KEY (miner_id, rom_hash)
);

-- Index for clustering queries
CREATE INDEX IF NOT EXISTS idx_rom_hash ON miner_rom_reports(rom_hash);

-- Flagged clusters
CREATE TABLE IF NOT EXISTS rom_clusters (
    cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rom_hash TEXT NOT NULL,
    hash_type TEXT NOT NULL,
    miners TEXT NOT NULL,           -- JSON array of miner_ids
    cluster_size INTEGER NOT NULL,
    is_known_emulator_rom INTEGER DEFAULT 0,
    known_rom_info TEXT,            -- JSON if known
    first_detected INTEGER NOT NULL,
    last_updated INTEGER NOT NULL
);

-- Miner flags for ROM violations
CREATE TABLE IF NOT EXISTS miner_rom_flags (
    miner_id TEXT PRIMARY KEY,
    flag_reason TEXT NOT NULL,
    cluster_id INTEGER,
    flagged_at INTEGER NOT NULL,
    resolved INTEGER DEFAULT 0,
    resolved_at INTEGER
);
"""


def init_rom_tables(db_path: str):
    """Initialize ROM clustering tables in the database."""
    conn = sqlite3.connect(db_path)
    conn.executescript(ROM_CLUSTERING_SCHEMA)
    conn.commit()
    conn.close()


class ROMClusteringServer:
    """
    Server-side ROM clustering detection.

    Tracks ROM hashes reported by miners and flags:
    1. Known emulator ROM hashes (from our database)
    2. Clustered ROMs (multiple miners with identical hash)
    """

    def __init__(self, db_path: str, cluster_threshold: int = 2):
        """
        Args:
            db_path: Path to SQLite database
            cluster_threshold: Number of miners sharing ROM before flagging
        """
        self.db_path = db_path
        self.cluster_threshold = cluster_threshold
        init_rom_tables(db_path)

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def process_rom_report(
        self,
        miner_id: str,
        rom_hash: str,
        hash_type: str = "sha1",
        platform: str = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Process a ROM hash report from a miner.

        Returns:
            (is_valid, reason, details)
        """
        now = int(time.time())
        rom_hash_lower = rom_hash.lower()

        conn = self._get_conn()
        cur = conn.cursor()

        # Check 1: Is this a known emulator ROM?
        if is_known_emulator_rom(rom_hash, hash_type):
            rom_info = identify_rom(rom_hash, hash_type)

            # Flag the miner
            cur.execute("""
                INSERT OR REPLACE INTO miner_rom_flags
                (miner_id, flag_reason, flagged_at)
                VALUES (?, ?, ?)
            """, (miner_id, f"known_emulator_rom:{rom_info}", now))

            conn.commit()
            conn.close()

            return False, "known_emulator_rom", rom_info

        # Check 2: Record the report
        cur.execute("""
            INSERT INTO miner_rom_reports
            (miner_id, rom_hash, hash_type, platform, first_seen, last_seen, report_count)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(miner_id, rom_hash) DO UPDATE SET
                last_seen = excluded.last_seen,
                report_count = report_count + 1
        """, (miner_id, rom_hash_lower, hash_type, platform, now, now))

        # Check 3: Look for clustering
        cur.execute("""
            SELECT miner_id FROM miner_rom_reports
            WHERE rom_hash = ? AND miner_id != ?
        """, (rom_hash_lower, miner_id))

        other_miners = [row[0] for row in cur.fetchall()]

        if len(other_miners) >= self.cluster_threshold:
            # Clustering detected!
            all_miners = [miner_id] + other_miners

            # Record the cluster
            import json
            cur.execute("""
                INSERT INTO rom_clusters
                (rom_hash, hash_type, miners, cluster_size, first_detected, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET
                    miners = excluded.miners,
                    cluster_size = excluded.cluster_size,
                    last_updated = excluded.last_updated
            """, (
                rom_hash_lower, hash_type,
                json.dumps(all_miners), len(all_miners),
                now, now
            ))

            cluster_id = cur.lastrowid

            # Flag all miners in the cluster
            for m in all_miners:
                cur.execute("""
                    INSERT OR REPLACE INTO miner_rom_flags
                    (miner_id, flag_reason, cluster_id, flagged_at)
                    VALUES (?, ?, ?, ?)
                """, (m, f"rom_cluster:{len(all_miners)}_miners", cluster_id, now))

            conn.commit()
            conn.close()

            return False, "rom_clustering", {
                "cluster_size": len(all_miners),
                "other_miners": other_miners,
                "rom_hash": rom_hash_lower,
            }

        conn.commit()
        conn.close()

        return True, "unique_rom", None

    def is_miner_flagged(self, miner_id: str) -> Tuple[bool, Optional[str]]:
        """Check if a miner is flagged for ROM violations."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT flag_reason FROM miner_rom_flags
            WHERE miner_id = ? AND resolved = 0
        """, (miner_id,))

        row = cur.fetchone()
        conn.close()

        if row:
            return True, row[0]
        return False, None

    def get_clusters(self) -> List[Dict]:
        """Get all detected ROM clusters."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT rom_hash, hash_type, miners, cluster_size,
                   is_known_emulator_rom, known_rom_info,
                   datetime(first_detected, 'unixepoch'),
                   datetime(last_updated, 'unixepoch')
            FROM rom_clusters
            ORDER BY cluster_size DESC
        """)

        import json
        clusters = []
        for row in cur.fetchall():
            clusters.append({
                "rom_hash": row[0],
                "hash_type": row[1],
                "miners": json.loads(row[2]),
                "cluster_size": row[3],
                "is_known_emulator": bool(row[4]),
                "known_rom_info": json.loads(row[5]) if row[5] else None,
                "first_detected": row[6],
                "last_updated": row[7],
            })

        conn.close()
        return clusters

    def get_flagged_miners(self) -> List[Dict]:
        """Get all flagged miners."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT miner_id, flag_reason, cluster_id,
                   datetime(flagged_at, 'unixepoch')
            FROM miner_rom_flags
            WHERE resolved = 0
        """)

        flagged = []
        for row in cur.fetchall():
            flagged.append({
                "miner_id": row[0],
                "reason": row[1],
                "cluster_id": row[2],
                "flagged_at": row[3],
            })

        conn.close()
        return flagged

    def get_stats(self) -> Dict:
        """Get ROM clustering statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM miner_rom_reports")
        total_reports = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT miner_id) FROM miner_rom_reports")
        unique_miners = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT rom_hash) FROM miner_rom_reports")
        unique_roms = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM rom_clusters")
        clusters = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM miner_rom_flags WHERE resolved = 0")
        flagged = cur.fetchone()[0]

        conn.close()

        return {
            "total_rom_reports": total_reports,
            "unique_miners_reporting": unique_miners,
            "unique_rom_hashes": unique_roms,
            "clusters_detected": clusters,
            "miners_flagged": flagged,
        }


def integrate_with_attestation(
    attestation_data: Dict,
    rom_server: ROMClusteringServer
) -> Tuple[bool, str]:
    """
    Integrate ROM checking with miner attestation.

    Call this from the /attest/submit endpoint handler.

    Args:
        attestation_data: The attestation payload from miner
        rom_server: ROMClusteringServer instance

    Returns:
        (is_valid, reason)
    """
    miner_id = attestation_data.get("miner_id") or attestation_data.get("miner")
    fingerprint = attestation_data.get("fingerprint", {})

    # Check if fingerprint includes ROM data
    rom_check = fingerprint.get("checks", {}).get("rom_fingerprint", {})

    if not rom_check or rom_check.get("skipped"):
        # No ROM data reported - OK for modern hardware
        return True, "no_rom_data"

    rom_data = rom_check.get("data", {})
    rom_hashes = rom_data.get("rom_hashes", {})

    # Process each reported ROM hash
    for platform, rom_hash in rom_hashes.items():
        if isinstance(rom_hash, dict):
            # Complex format with hash_type
            hash_val = rom_hash.get("hash") or rom_hash.get("header_md5")
            hash_type = rom_hash.get("hash_type", "md5")
        else:
            hash_val = rom_hash
            hash_type = "sha1"  # Default

        if hash_val:
            is_valid, reason, details = rom_server.process_rom_report(
                miner_id, hash_val, hash_type, platform
            )

            if not is_valid:
                return False, f"{reason}:{details}"

    return True, "rom_check_passed"


if __name__ == "__main__":
    import tempfile
    import os

    print("ROM Clustering Server - Test")
    print("=" * 50)

    # Create temp database
    db_path = "/tmp/test_rom_clustering.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    server = ROMClusteringServer(db_path, cluster_threshold=2)

    # Test 1: Known emulator ROM
    print("\n[Test 1] Known emulator ROM:")
    result = server.process_rom_report(
        "fake-amiga-miner",
        "891e9a547772fe0c6c19b610baf8bc4ea7fcb785",  # Kickstart 1.3
        "sha1",
        "amiga"
    )
    print(f"  Result: {result}")

    # Test 2: Unique ROM
    print("\n[Test 2] Unique ROM:")
    result = server.process_rom_report(
        "real-vintage-mac",
        "abcd1234unique5678hash",
        "apple",
        "mac_68k"
    )
    print(f"  Result: {result}")

    # Test 3: Clustering detection
    print("\n[Test 3] ROM Clustering:")
    for i in range(3):
        result = server.process_rom_report(
            f"suspicious-miner-{i}",
            "deadbeef1234same5678hash",
            "md5",
            "mac_ppc"
        )
        print(f"  Miner {i}: {result}")

    # Stats
    print("\n[Stats]")
    stats = server.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Clusters
    print("\n[Clusters]")
    for cluster in server.get_clusters():
        print(f"  {cluster}")

    # Flagged miners
    print("\n[Flagged Miners]")
    for miner in server.get_flagged_miners():
        print(f"  {miner}")

    # Cleanup
    os.remove(db_path)
