"""PoW dual-mining proof validation helpers (server-side scaffold)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, Tuple

POW_BONUS = {
    "node_rpc": 1.5,
    "pool_account": 1.3,
    "process_detection": 1.15,
}


def ensure_pow_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pow_mining_proofs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id TEXT NOT NULL,
            proof_type TEXT NOT NULL,
            chain TEXT,
            proof_nonce TEXT,
            proof_hash TEXT NOT NULL,
            observed_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            bonus_multiplier REAL NOT NULL,
            status TEXT NOT NULL,
            details_json TEXT,
            UNIQUE(miner_id, proof_hash)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pow_mining_proofs_miner_time ON pow_mining_proofs(miner_id, observed_at)"
    )


def _stable_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_pow_proof_payload(
    proof: Dict[str, Any] | None,
    nonce: str | None,
    now_ts: int | None = None,
) -> Tuple[bool, Dict[str, Any]]:
    now_ts = int(now_ts or time.time())

    if not proof:
        return False, {"reason": "missing_pow_proof", "bonus_multiplier": 1.0}

    proof_type = (proof.get("proof_type") or "").strip().lower()
    if proof_type not in POW_BONUS:
        return False, {"reason": "unsupported_proof_type", "bonus_multiplier": 1.0, "proof_type": proof_type}

    expires_at = int(proof.get("expires_at") or 0)
    if expires_at <= now_ts:
        return False, {"reason": "proof_expired", "bonus_multiplier": 1.0, "proof_type": proof_type}

    if expires_at > now_ts + 900:
        return False, {"reason": "proof_ttl_too_long", "bonus_multiplier": 1.0, "proof_type": proof_type}

    proof_nonce = proof.get("nonce")
    if nonce and proof_nonce and str(proof_nonce) != str(nonce):
        return False, {"reason": "nonce_binding_failed", "bonus_multiplier": 1.0, "proof_type": proof_type}

    return True, {
        "reason": "ok",
        "bonus_multiplier": POW_BONUS[proof_type],
        "proof_type": proof_type,
        "chain": proof.get("chain"),
        "proof_nonce": proof_nonce,
        "expires_at": expires_at,
        "proof_hash": _stable_hash(proof),
    }


def record_pow_proof(conn: sqlite3.Connection, miner_id: str, validation: Dict[str, Any], proof: Dict[str, Any], status: str) -> None:
    ensure_pow_tables(conn)
    conn.execute(
        """
        INSERT OR IGNORE INTO pow_mining_proofs
        (miner_id, proof_type, chain, proof_nonce, proof_hash, observed_at, expires_at, bonus_multiplier, status, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            miner_id,
            validation.get("proof_type", "unknown"),
            validation.get("chain"),
            validation.get("proof_nonce"),
            validation.get("proof_hash") or _stable_hash(proof or {}),
            int(time.time()),
            int(validation.get("expires_at") or int(time.time())),
            float(validation.get("bonus_multiplier") or 1.0),
            status,
            json.dumps({"validation": validation, "proof": proof}, ensure_ascii=False),
        ),
    )
