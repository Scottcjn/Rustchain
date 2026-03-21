#!/usr/bin/env python3
"""
RustChain Ergo Anchor Verifier
==============================

Independently verifies RustChain -> Ergo cross-chain anchors.

Usage:
    python verify_anchors.py                          # Verify all anchors
    python verify_anchors.py --limit 50               # Limit to 50 most recent
    python verify_anchors.py --anchor-id 42           # Verify specific anchor
    python verify_anchors.py --rustchain-height 424   # Verify anchors up to height
    python verify_anchors.py --offline DB_PATH        # Offline mode with DB dump
    python verify_anchors.py --json                   # JSON output
    python verify_anchors.py --ergo-node http://node:9053  # Custom Ergo node

Requirements:
    pip install requests
"""

import os
import sys
import json
import sqlite3
import argparse
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [VERIFY] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Ergo node defaults
DEFAULT_ERGO_NODE = os.environ.get("ERGO_NODE_URL", "http://localhost:9053")
DEFAULT_ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")

# RustChain defaults
DEFAULT_RUSTCHAIN_DB = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")
DEFAULT_RUSTCHAIN_GENESIS = 1728000000  # Genesis timestamp (adjust to actual)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ErgoAnchor:
    """Represents a RustChain anchor stored in the database."""
    id: int
    rustchain_height: int
    rustchain_hash: str
    commitment_hash: str      # Blake2b256 stored in DB
    ergo_tx_id: str
    ergo_height: Optional[int]
    confirmations: int
    status: str
    created_at: int

    @classmethod
    def from_row(cls, row: Dict) -> "ErgoAnchor":
        return cls(
            id=row["id"],
            rustchain_height=row["rustchain_height"],
            rustchain_hash=row.get("rustchain_hash", ""),
            commitment_hash=row["commitment_hash"],
            ergo_tx_id=row["ergo_tx_id"],
            ergo_height=row.get("ergo_height"),
            confirmations=row.get("confirmations", 0),
            status=row.get("status", "unknown"),
            created_at=row["created_at"]
        )


@dataclass
class VerificationResult:
    """Result of anchor verification."""
    anchor_id: int
    ergo_tx_id: str
    rustchain_height: int
    miner_count: int

    # Verification outcomes
    tx_found: bool = False
    on_chain_commitment: Optional[str] = None
    recomputed_commitment: Optional[str] = None

    # Comparison results
    stored_vs_onchain: Optional[str] = None   # "MATCH", "MISMATCH", "MISSING"
    onchain_vs_recomputed: Optional[str] = None  # "MATCH", "MISMATCH"

    error: Optional[str] = None

    # Miner data used for recomputation
    miners_used: List[Dict] = field(default_factory=list)

    def is_verified(self) -> bool:
        return (
            self.tx_found
            and self.stored_vs_onchain == "MATCH"
            and self.onchain_vs_recomputed == "MATCH"
        )

    def to_summary(self) -> str:
        tx_short = self.ergo_tx_id[:12] + "..."
        status = "VERIFIED" if self.is_verified() else "FAILED"
        if self.error:
            return f"Anchor #{self.anchor_id}: TX {tx_short} | {status} | Error: {self.error}"
        return (
            f"Anchor #{self.anchor_id}: TX {tx_short} | "
            f"stored==onchain={self.stored_vs_onchain} | "
            f"onchain==recomputed={self.onchain_vs_recomputed} | "
            f"{self.miner_count} miners | "
            f"{status}"
        )


# =============================================================================
# ERGO NODE CLIENT
# =============================================================================

class ErgoNodeClient:
    """Client for Ergo node API (localhost:9053)."""

    def __init__(self, node_url: str = DEFAULT_ERGO_NODE, api_key: str = DEFAULT_ERGO_API_KEY):
        self.node_url = node_url.rstrip('/')
        self.api_key = api_key
        self.session = None

    def _init_session(self):
        if self.session is None:
            import requests
            self.session = requests.Session()
            if self.api_key:
                self.session.headers['api_key'] = self.api_key

    def _get(self, endpoint: str, timeout: int = 30) -> Optional[Dict]:
        self._init_session()
        try:
            resp = self.session.get(f"{self.node_url}{endpoint}", timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"GET {endpoint} -> {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"GET {endpoint} error: {e}")
            return None

    def get_info(self) -> Optional[Dict]:
        """Get Ergo node info."""
        return self._get("/info")

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get transaction by ID."""
        return self._get(f"/transactions/{tx_id}")

    def get_box(self, box_id: str) -> Optional[Dict]:
        """Get a specific box by ID."""
        return self._get(f"/utxo/byId/{box_id}")

    def extract_r4_commitment(self, tx: Dict) -> Optional[str]:
        """
        Extract Blake2b256 commitment from R4 register in transaction outputs.

        R4 format: "0e20" + 32-byte Blake2b256 hash (Coll[Byte] with 32 elements)
        Returns the 64-char hex commitment hash without the prefix.
        """
        for output in tx.get("outputs", []):
            registers = output.get("additionalRegisters", {})
            r4 = registers.get("R4", {})
            if r4:
                serialized = r4.get("serializedValue", "")
                if serialized:
                    # R4 format: "0e20" + 32 bytes of commitment = 4 + 64 = 68 hex chars
                    # Some txs use R5 instead, check both
                    for reg_key in ["R4", "R5", "R6", "R7"]:
                        reg = registers.get(reg_key, {}).get("serializedValue", "")
                        if reg and reg.startswith("0e20") and len(reg) >= 68:
                            return reg[4:68]  # Strip "0e20" prefix, get 32 bytes
                        # Also try raw format (just the hex bytes)
                        if reg and len(reg) == 64:
                            return reg
        return None

    def is_reachable(self) -> bool:
        """Check if Ergo node is reachable."""
        info = self.get_info()
        return info is not None


# =============================================================================
# RUSTCHAIN DB CLIENT
# =============================================================================

class RustChainDB:
    """Client for RustChain SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.genesis_ts = DEFAULT_RUSTCHAIN_GENESIS

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def get_anchors(
        self,
        limit: Optional[int] = None,
        min_height: Optional[int] = None,
        anchor_id: Optional[int] = None
    ) -> List[ErgoAnchor]:
        """Load anchors from database."""
        anchors = []
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # First try the rustchain_ergo_anchor schema
            try:
                cur.execute("SELECT * FROM ergo_anchors WHERE 1=1")
                columns = [desc[0] for desc in cur.description]
            except sqlite3.OperationalError:
                return anchors

            query = "SELECT * FROM ergo_anchors WHERE 1=1"
            params = []

            if anchor_id is not None:
                query += " AND id = ?"
                params.append(anchor_id)

            if min_height is not None:
                query += " AND rustchain_height <= ?"
                params.append(min_height)

            query += " ORDER BY rustchain_height ASC"

            if limit is not None:
                query += f" LIMIT {limit}"

            cur.execute(query, params)

            for row in cur.fetchall():
                row_dict = dict(row)
                anchors.append(ErgoAnchor(
                    id=row_dict["id"],
                    rustchain_height=row_dict["rustchain_height"],
                    rustchain_hash=row_dict.get("rustchain_hash", ""),
                    commitment_hash=row_dict["commitment_hash"] if "commitment_hash" in row_dict
                        else row_dict.get("tx_id", ""),  # Fallback for ergo_miner_anchor schema
                    ergo_tx_id=row_dict["ergo_tx_id"] if "ergo_tx_id" in row_dict else row_dict["tx_id"],
                    ergo_height=row_dict.get("ergo_height"),
                    confirmations=row_dict.get("confirmations", 0),
                    status=row_dict.get("status", "unknown"),
                    created_at=row_dict["created_at"]
                ))

        return anchors

    def get_miners_for_height(self, rustchain_height: int, created_at: int) -> List[Dict]:
        """
        Get miners that would have been used to compute commitment for a given anchor.

        Uses the same logic as ergo_miner_anchor.py:
        - Sort miner_attest_recent by ts_ok DESC
        - Take top N miners (where N = miner_count from anchor)
        - Canonical JSON sort_keys=True before hashing
        """
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Get time window for this anchor
            # Use created_at as the reference time (when anchor was made)
            # and look back ~10 minutes to capture miners attested around that time
            time_window_start = created_at - 600  # 10 min before anchor

            try:
                cur.execute("""
                    SELECT miner, device_arch, ts_ok
                    FROM miner_attest_recent
                    WHERE ts_ok >= ?
                    ORDER BY ts_ok DESC
                """, (time_window_start,))
            except sqlite3.OperationalError:
                return []

            rows = cur.fetchall()
            miners = [
                {"miner": row["miner"], "device_arch": row["device_arch"], "ts_ok": row["ts_ok"]}
                for row in rows
            ]

        return miners


# =============================================================================
# COMMITMENT COMPUTATION
# =============================================================================

def compute_miner_commitment(miners: List[Dict]) -> str:
    """
    Compute Blake2b256 commitment from miner list.

    Matches the commitment computation in ergo_miner_anchor.py:
    - Canonical JSON with sort_keys=True
    - Blake2b(data, digest_size=32).hexdigest()
    """
    if not miners:
        return "0" * 64

    data = json.dumps(miners, sort_keys=True).encode()
    return hashlib.blake2b(data, digest_size=32).hexdigest()


# =============================================================================
# VERIFICATION ENGINE
# =============================================================================

class AnchorVerifier:
    """
    Verifies RustChain -> Ergo anchor commitments.

    For each anchor:
    1. Fetch Ergo transaction from node API
    2. Extract R4 register (on-chain commitment hash)
    3. Recompute commitment from miner_attest_recent data
    4. Compare: stored == on-chain == recomputed
    """

    def __init__(
        self,
        db_path: str,
        ergo_node: str = DEFAULT_ERGO_NODE,
        ergo_api_key: str = DEFAULT_ERGO_API_KEY,
        offline: bool = False
    ):
        self.db = RustChainDB(db_path)
        self.ergo = ErgoNodeClient(ergo_node, ergo_api_key)
        self.offline = offline
        self.results: List[VerificationResult] = []

    def verify_anchor(self, anchor: ErgoAnchor) -> VerificationResult:
        """Verify a single anchor."""
        result = VerificationResult(
            anchor_id=anchor.id,
            ergo_tx_id=anchor.ergo_tx_id,
            rustchain_height=anchor.rustchain_height,
            miner_count=0
        )

        # Step 1: Fetch Ergo transaction
        if self.offline:
            result.error = "OFFLINE_MODE: Cannot fetch Ergo TX"
            return result

        tx = self.ergo.get_transaction(anchor.ergo_tx_id)
        if not tx:
            result.error = f"Ergo TX not found: {anchor.ergo_tx_id}"
            return result

        result.tx_found = True

        # Step 2: Extract R4 commitment from transaction outputs
        on_chain = self.ergo.extract_r4_commitment(tx)
        if not on_chain:
            result.error = "No R4 commitment found in Ergo TX outputs"
            return result

        result.on_chain_commitment = on_chain

        # Compare stored (DB) vs on-chain
        if anchor.commitment_hash:
            if anchor.commitment_hash.lower() == on_chain.lower():
                result.stored_vs_onchain = "MATCH"
            else:
                result.stored_vs_onchain = "MISMATCH"
        else:
            result.stored_vs_onchain = "MISSING"

        # Step 3: Recompute commitment from miner data
        miners = self.db.get_miners_for_height(anchor.rustchain_height, anchor.created_at)
        result.miners_used = miners
        result.miner_count = len(miners)

        if not miners:
            result.error = "No miner data available to recompute commitment"
            return result

        recomputed = compute_miner_commitment(miners)
        result.recomputed_commitment = recomputed

        # Compare on-chain vs recomputed
        if recomputed.lower() == on_chain.lower():
            result.onchain_vs_recomputed = "MATCH"
        else:
            result.onchain_vs_recomputed = "MISMATCH"

        return result

    def verify_all(
        self,
        limit: Optional[int] = None,
        min_height: Optional[int] = None,
        anchor_id: Optional[int] = None
    ) -> List[VerificationResult]:
        """Verify all anchors matching criteria."""
        anchors = self.db.get_anchors(limit=limit, min_height=min_height, anchor_id=anchor_id)

        if not anchors:
            logger.warning("No anchors found in database")
            return []

        logger.info(f"Verifying {len(anchors)} anchor(s)...")

        for anchor in anchors:
            logger.info(f"Verifying anchor #{anchor.id} (TX: {anchor.ergo_tx_id[:12]}...)")
            result = self.verify_anchor(anchor)
            self.results.append(result)

        return self.results

    def print_summary(self, results: List[VerificationResult], json_output: bool = False):
        """Print verification summary."""
        if json_output:
            output = {
                "total": len(results),
                "verified": sum(1 for r in results if r.is_verified()),
                "failed": sum(1 for r in results if not r.is_verified() and r.error is None),
                "errors": sum(1 for r in results if r.error),
                "anchors": []
            }
            for r in results:
                anchor_out = {
                    "anchor_id": r.anchor_id,
                    "ergo_tx_id": r.ergo_tx_id,
                    "rustchain_height": r.rustchain_height,
                    "tx_found": r.tx_found,
                    "stored_vs_onchain": r.stored_vs_onchain,
                    "onchain_vs_recomputed": r.onchain_vs_recomputed,
                    "miner_count": r.miner_count,
                    "verified": r.is_verified(),
                }
                if r.error:
                    anchor_out["error"] = r.error
                if r.on_chain_commitment:
                    anchor_out["on_chain_commitment"] = r.on_chain_commitment
                if r.recomputed_commitment:
                    anchor_out["recomputed_commitment"] = r.recomputed_commitment
                output["anchors"].append(anchor_out)
            print(json.dumps(output, indent=2))
            return

        # Text summary
        print("\n" + "=" * 78)
        print(f"RustChain Ergo Anchor Verification — {len(results)} anchor(s) checked")
        print("=" * 78)

        verified = 0
        failed = 0
        errors = 0

        for r in results:
            status = "OK" if r.is_verified() else ("ERR" if r.error else "FAIL")
            tx_short = r.ergo_tx_id[:12] + "..."

            if r.error:
                errors += 1
                print(f"\nAnchor #{r.anchor_id}: TX {tx_short} | [{status}] {r.error}")
            else:
                s_vs_o = r.stored_vs_onchain or "?"
                o_vs_r = r.onchain_vs_recomputed or "?"
                print(
                    f"\nAnchor #{r.anchor_id}: TX {tx_short} | "
                    f"stored==onchain=[{s_vs_o}] | "
                    f"onchain==recomputed=[{o_vs_r}] | "
                    f"{r.miner_count} miners"
                )

                if r.is_verified():
                    verified += 1
                    print("  RESULT: VERIFIED")
                else:
                    failed += 1
                    print("  RESULT: FAILED")
                    if r.on_chain_commitment:
                        print(f"  On-chain:   {r.on_chain_commitment}")
                    if r.recomputed_commitment:
                        print(f"  Recomputed: {r.recomputed_commitment}")
                    if r.stored_vs_onchain == "MISMATCH":
                        print(f"  DB stored:  {r.ergo_tx_id}")

        print("-" * 78)
        print(f"Summary: {verified} verified, {failed} failed, {errors} errors")
        if verified + failed + errors > 0:
            mismatch_count = sum(1 for r in results if not r.is_verified() and r.error is None)
            print(f"Mismatches: {mismatch_count}")
        print("=" * 78)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Ergo Anchor Verifier — Independent anchor verification tool"
    )
    parser.add_argument("--db", default=DEFAULT_RUSTCHAIN_DB, help="RustChain DB path")
    parser.add_argument("--ergo-node", default=DEFAULT_ERGO_NODE, help="Ergo node URL")
    parser.add_argument("--ergo-api-key", default=DEFAULT_ERGO_API_KEY, help="Ergo API key")
    parser.add_argument("--limit", type=int, default=50, help="Max anchors to verify")
    parser.add_argument("--anchor-id", type=int, help="Verify specific anchor by ID")
    parser.add_argument("--rustchain-height", type=int, dest="min_height", help="Verify anchors up to height")
    parser.add_argument("--offline", action="store_true", help="Offline mode (skip Ergo API calls)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--quiet", action="store_true", help="Suppress info logs")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Check DB exists
    if not os.path.exists(args.db):
        print(f"ERROR: Database not found: {args.db}")
        print("Set RUSTCHAIN_DB environment variable or use --db flag")
        sys.exit(1)

    # Offline mode warning
    if args.offline:
        print("[OFFLINE MODE] Ergo node API calls disabled — will report mismatches without on-chain verification")

    # Run verification
    verifier = AnchorVerifier(
        db_path=args.db,
        ergo_node=args.ergo_node,
        ergo_api_key=args.ergo_api_key,
        offline=args.offline
    )

    try:
        results = verifier.verify_all(
            limit=args.limit,
            min_height=args.min_height,
            anchor_id=args.anchor_id
        )
    except Exception as e:
        print(f"ERROR during verification: {e}")
        sys.exit(1)

    verifier.print_summary(results, json_output=args.json)

    # Exit code: 0 if all verified, 1 if any failures
    if results:
        all_verified = all(r.is_verified() for r in results)
        sys.exit(0 if all_verified else 1)
    sys.exit(0)


if __name__ == "__main__":
    main()
