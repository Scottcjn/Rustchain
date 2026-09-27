#!/usr/bin/env python3
"""
Ergo Miner Anchor - Zero-fee anchor TX with miner + beacon commitments in registers.

Updated to include beacon envelope digest in the R4 commitment.
Combined commitment: blake2b(miner_commitment + "|" + beacon_digest)

Security: Post-broadcast TX verification prevents fake anchor records.
"""
import os, json, sqlite3, time, requests
from hashlib import blake2b

ERGO_NODE = os.environ.get("ERGO_NODE", "http://localhost:9053")

ENV_FILE = os.environ.get("RUSTCHAIN_ENV_FILE", "/root/rustchain/.env")


def _from_env_file(name, path=None):
    """Fallback: read NAME from the node's .env when not exported (cron does not source it)."""
    try:
        for line in open(path or ENV_FILE):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _ergo_key_from_env_file(path=None):
    return _from_env_file("ERGO_API_KEY", path)


ERGO_API_KEY = os.environ.get("ERGO_API_KEY") or _ergo_key_from_env_file()
# Wallet unlock password: env or .env only. Never a hard-coded default in source.
ERGO_WALLET_PASS = os.environ.get("ERGO_WALLET_PASS") or _from_env_file("ERGO_WALLET_PASS")
DB_PATH = "/root/rustchain/rustchain_v2.db"
ANCHOR_VALUE = 1000000  # 0.001 ERG min box size

# Verification settings
VERIFY_POLL_INTERVAL = 10   # seconds between verification polls
VERIFY_MAX_WAIT = 120       # max seconds to wait for TX to appear
VERIFY_CONFIRM_DEPTH = 1    # min confirmations to mark as confirmed

# Import beacon anchor functions
from beacon_anchor import compute_beacon_digest, mark_anchored, init_beacon_table


def verify_ergo_tx(session, tx_id):
    """
    Verify a transaction exists on the Ergo blockchain.

    Uses /wallet/transactionById (works on private chains without extra indexing)
    and falls back to mempool check.
    Returns (exists: bool, confirmed: bool, error: str|None).
    """
    if not tx_id or not isinstance(tx_id, str) or len(tx_id) < 32:
        return False, False, "invalid_tx_id"

    # Check via wallet API (works on private chains, returns numConfirmations)
    try:
        resp = session.get(
            ERGO_NODE + f"/wallet/transactionById?id={tx_id}",
            timeout=10
        )
        if resp.status_code == 200:
            tx_data = resp.json()
            # Verify it has outputs (not a stub/empty response)
            if tx_data.get("outputs") and len(tx_data["outputs"]) > 0:
                num_confs = tx_data.get("numConfirmations", 0)
                confirmed = num_confs >= VERIFY_CONFIRM_DEPTH
                return True, confirmed, None
    except Exception as e:
        pass  # Fall through to mempool check

    # Check unconfirmed/mempool
    try:
        resp = session.get(
            ERGO_NODE + "/transactions/unconfirmed",
            timeout=10
        )
        if resp.status_code == 200:
            mempool = resp.json()
            for tx in mempool:
                if tx.get("id") == tx_id:
                    return True, False, None
    except Exception as e:
        return False, False, f"mempool_check_error: {e}"

    return False, False, "tx_not_found"


def verify_anchor_commitment(session, tx_id, expected_commitment):
    """
    Verify that a confirmed Ergo TX contains the expected commitment in R4.

    This prevents an attacker from submitting a valid but unrelated tx_id
    and claiming it anchors our data.

    Uses /wallet/transactionById (works on private chains without extra indexing).
    Returns (valid: bool, error: str|None).
    """
    if not tx_id or not expected_commitment:
        return False, "missing_tx_id_or_commitment"

    try:
        resp = session.get(
            ERGO_NODE + f"/wallet/transactionById?id={tx_id}",
            timeout=10
        )
        if resp.status_code != 200:
            return False, f"tx_fetch_failed: HTTP {resp.status_code}"

        tx_data = resp.json()
        for output in tx_data.get("outputs", []):
            registers = output.get("additionalRegisters", {})
            r4 = registers.get("R4", {})
            # R4 can be a string (raw hex) or dict with serializedValue
            r4_hex = r4 if isinstance(r4, str) else r4.get("serializedValue", "")

            # Our encoding: "0e20" + 32-byte hex commitment
            # 0e = Coll[Byte], 20 = VLQ(32)
            expected_r4 = "0e20" + expected_commitment
            if r4_hex == expected_r4:
                return True, None

        return False, "commitment_not_found_in_tx_outputs"
    except Exception as e:
        return False, f"verification_error: {e}"


class ErgoMinerAnchor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["api_key"] = ERGO_API_KEY
        self.session.headers["Content-Type"] = "application/json"

    def unlock_wallet(self, password=None):
        """Unlock wallet if needed. The password comes from ERGO_WALLET_PASS
        (environment or .env); there is deliberately no default in source."""
        password = password or ERGO_WALLET_PASS
        status = self.session.get(ERGO_NODE + "/wallet/status").json()
        if not status.get("isUnlocked"):
            if not password:
                print("  WARNING: wallet locked and ERGO_WALLET_PASS not set; signing will fail")
                return
            self.session.post(ERGO_NODE + "/wallet/unlock", json={"pass": password})

    def get_recent_miners(self, limit=10):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT miner, device_arch, ts_ok FROM miner_attest_recent ORDER BY ts_ok DESC LIMIT ?", (limit,))
        miners = [dict(row) for row in cur.fetchall()]  # fetchall-ok: already-paginated (LIMIT ?)
        conn.close()
        return miners

    @staticmethod
    def canonical_miner_data(miners):
        """Exact preimage of the miner commitment. Stored in ergo_anchors.miner_data
        so a third party can recompute and check every anchor."""
        return json.dumps(miners, sort_keys=True)

    def compute_commitment(self, miners):
        data = self.canonical_miner_data(miners).encode()
        return blake2b(data, digest_size=32).hexdigest()

    def get_rc_slot(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT MAX(slot) FROM headers")
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else 0

    def compute_combined_commitment(self, miner_commitment, beacon_info):
        """
        Combine miner commitment with beacon digest.
        If no beacon envelopes pending, use miner commitment alone.
        """
        beacon_digest = beacon_info.get("digest")
        if beacon_digest:
            combined = f"{miner_commitment}|{beacon_digest}".encode()
            return blake2b(combined, digest_size=32).hexdigest()
        else:
            return miner_commitment

    def _wait_for_tx(self, tx_id, commitment, max_wait=VERIFY_MAX_WAIT):
        """
        Wait for a broadcast TX to appear on the Ergo node (mempool or confirmed).

        Returns (verified: bool, confirmed: bool, error: str|None).
        """
        start = time.time()
        last_error = None

        while time.time() - start < max_wait:
            exists, confirmed, err = verify_ergo_tx(self.session, tx_id)
            if exists:
                print(f"  TX verified on Ergo ({'confirmed' if confirmed else 'in mempool'})")

                # If confirmed, also verify the commitment matches R4
                if confirmed:
                    valid, verr = verify_anchor_commitment(
                        self.session, tx_id, commitment
                    )
                    if not valid:
                        print(f"  WARNING: TX exists but commitment mismatch: {verr}")
                        return False, False, f"commitment_mismatch: {verr}"

                return True, confirmed, None

            last_error = err
            time.sleep(VERIFY_POLL_INTERVAL)

        return False, False, f"tx_not_found_after_{max_wait}s: {last_error}"

    def verify_past_anchors(self):
        """
        Verify all anchors with status='local' or status='pending'.
        Updates status to 'confirmed' or 'failed' based on Ergo node state.

        This catches records from previous runs that were stored before
        verification could complete.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Add status column if missing (old schema had no status)
        try:
            cur.execute("ALTER TABLE ergo_anchors ADD COLUMN status TEXT DEFAULT 'local'")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        cur.execute(
            "SELECT id, tx_id, commitment, status, created_at FROM ergo_anchors "
            "WHERE status IN ('local', 'pending') ORDER BY id ASC LIMIT 200"
        )
        # Oldest first, at most 200 per run; any remainder is picked up next run.
        rows = cur.fetchall()  # fetchall-ok: already-paginated (LIMIT 200)
        conn.close()

        if not rows:
            return

        print(f"\n=== Verifying {len(rows)} unconfirmed anchor(s) ===")
        for row in rows:
            anchor_id = row["id"]
            tx_id = row["tx_id"]
            commitment = row["commitment"]
            old_status = row["status"]
            created_at = row["created_at"] or 0

            # Skip rows with missing tx_id or commitment
            if not tx_id or not commitment:
                print(f"  Anchor #{anchor_id}: SKIPPED - missing tx_id or commitment")
                continue

            exists, confirmed, err = verify_ergo_tx(self.session, tx_id)

            if confirmed:
                # Double-check commitment in R4
                valid, verr = verify_anchor_commitment(
                    self.session, tx_id, commitment
                )
                if valid:
                    new_status = "confirmed"
                    print(f"  Anchor #{anchor_id} ({tx_id[:16]}...): CONFIRMED on-chain")
                else:
                    new_status = "commitment_mismatch"
                    print(f"  Anchor #{anchor_id} ({tx_id[:16]}...): TX exists but commitment MISMATCH - {verr}")
            elif exists:
                new_status = "pending"  # In mempool, not yet confirmed
                print(f"  Anchor #{anchor_id} ({tx_id[:16]}...): in mempool (pending)")
            else:
                # TX not found -- could be dropped from mempool or never broadcast
                # Only mark as failed if old enough (>1 hour)
                age = int(time.time()) - created_at if created_at else 0
                if age > 3600:
                    new_status = "failed"
                    print(f"  Anchor #{anchor_id} ({tx_id[:16]}...): FAILED - not found after {age}s")
                else:
                    new_status = old_status  # Keep current status, too early to call it failed
                    print(f"  Anchor #{anchor_id} ({tx_id[:16]}...): not yet found (age={age}s, keeping '{old_status}')")

            if new_status != old_status:
                conn2 = sqlite3.connect(DB_PATH)
                conn2.execute(
                    "UPDATE ergo_anchors SET status = ? WHERE id = ?",
                    (new_status, anchor_id)
                )
                conn2.commit()
                conn2.close()

    def create_anchor_tx(self, miners):
        """Create zero-fee anchor TX with miner + beacon data in registers."""
        self.unlock_wallet()

        miner_commitment = self.compute_commitment(miners)
        beacon_info = compute_beacon_digest(DB_PATH)
        commitment = self.compute_combined_commitment(miner_commitment, beacon_info)
        rc_slot = self.get_rc_slot()

        # Get UTXO
        boxes = self.session.get(ERGO_NODE + "/wallet/boxes/unspent?minConfirmations=1").json()
        input_box = None
        for b in boxes:
            box = b.get("box", {})
            if box.get("value", 0) >= 2 * ANCHOR_VALUE:
                input_box = box
                break

        if not input_box:
            return {"success": False, "error": "No UTXO"}

        box_bytes = self.session.get(ERGO_NODE + "/utxo/byIdBinary/" + input_box["boxId"]).json().get("bytes")
        height = self.session.get(ERGO_NODE + "/info").json().get("fullHeight", 0)

        input_val = input_box["value"]
        change_val = input_val - ANCHOR_VALUE  # Zero fee

        beacon_count = beacon_info["count"]
        beacon_digest = beacon_info.get("digest", "")

        print("Creating anchor TX:")
        print("  Miner commitment:", miner_commitment[:32] + "...")
        if beacon_count > 0:
            print("  Beacon digest:   ", beacon_digest[:32] + "...")
            print("  Beacon envelopes:", beacon_count)
        print("  Combined commit: ", commitment[:32] + "...")
        print("  Miners:", len(miners))
        print("  RC Slot:", rc_slot)
        print("  Input:", input_val / 1e9, "ERG")

        unsigned_tx = {
            "inputs": [{"boxId": input_box["boxId"], "extension": {}}],
            "dataInputs": [],
            "outputs": [
                {
                    "value": ANCHOR_VALUE,
                    "ergoTree": input_box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": {
                        "R4": "0e20" + commitment  # 32-byte combined commitment
                    }
                },
                {
                    "value": change_val,
                    "ergoTree": input_box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": {}
                }
            ]
        }

        # Sign
        sign_resp = self.session.post(ERGO_NODE + "/wallet/transaction/sign",
            json={"tx": unsigned_tx, "inputsRaw": [box_bytes], "dataInputsRaw": []})

        if sign_resp.status_code != 200:
            return {"success": False, "error": "Sign failed: " + sign_resp.text[:100]}

        signed = sign_resp.json()

        # Broadcast
        send_resp = self.session.post(ERGO_NODE + "/transactions", json=signed)

        if send_resp.status_code == 200:
            tx_id = send_resp.json()
            print("  Broadcast OK. TX:", tx_id)

            # --- SECURITY FIX: Verify TX exists on Ergo before storing ---
            print("  Verifying TX on Ergo node...")
            verified, confirmed, verr = self._wait_for_tx(tx_id, commitment)

            if not verified:
                print(f"  VERIFICATION FAILED: {verr}")
                print("  Anchor record NOT stored. TX may have been dropped.")
                return {
                    "success": False,
                    "error": f"tx_verification_failed: {verr}",
                    "tx_id": str(tx_id)
                }

            status = "confirmed" if confirmed else "pending"
            # --- END SECURITY FIX ---

            # Save to DB with beacon fields and verified status
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # Ensure table has beacon columns (additive migration)
            try:
                cur.execute("ALTER TABLE ergo_anchors ADD COLUMN beacon_count INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                cur.execute("ALTER TABLE ergo_anchors ADD COLUMN beacon_digest TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cur.execute("ALTER TABLE ergo_anchors ADD COLUMN miner_data TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # miner_data = the commitment preimage. Without it nobody can recompute
            # a historical commitment (miner_attest_recent is overwritten
            # continuously), so the anchor proves nothing to an outside auditor.
            # Recompute: blake2b(miner_data) = miner commitment; if beacon_digest is
            # set, blake2b(miner_commitment + "|" + beacon_digest) = commitment.
            cur.execute(
                "INSERT INTO ergo_anchors (tx_id, commitment, miner_count, miner_data, rc_slot, created_at, beacon_count, beacon_digest, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(tx_id), commitment, len(miners), self.canonical_miner_data(miners), rc_slot, int(time.time()),
                 beacon_count, beacon_digest, status)
            )
            conn.commit()
            conn.close()

            # Mark beacon envelopes as anchored
            if beacon_info["ids"]:
                mark_anchored(beacon_info["ids"], DB_PATH)
                print(f"  Marked {len(beacon_info['ids'])} beacon envelopes as anchored")

            return {
                "success": True,
                "tx_id": tx_id,
                "commitment": commitment,
                "miner_commitment": miner_commitment,
                "beacon_count": beacon_count,
                "beacon_digest": beacon_digest,
                "status": status,
                "verified": True
            }
        else:
            return {"success": False, "error": send_resp.text[:150]}

    def anchor_miners(self):
        miners = self.get_recent_miners(10)
        if not miners:
            return {"success": False, "error": "No miners"}

        print("\n=== Anchoring", len(miners), "miners to Ergo ===")
        for m in miners:
            print("  -", m.get("miner", "?")[:20] + ":", m.get("device_arch", "?"))

        beacon_info = compute_beacon_digest(DB_PATH)
        if beacon_info["count"] > 0:
            print(f"  + {beacon_info['count']} beacon envelopes pending")

        return self.create_anchor_tx(miners)


if __name__ == "__main__":
    # Ensure beacon table exists
    init_beacon_table(DB_PATH)

    anchor = ErgoMinerAnchor()

    # First: verify any past unconfirmed anchors
    anchor.verify_past_anchors()

    # Then: create new anchor
    result = anchor.anchor_miners()
    print("\nResult:", json.dumps(result, indent=2))
