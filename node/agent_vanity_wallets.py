#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Agent vanity wallets for RustChain.

This module implements the first milestone of rustchain-bounties#30:
deterministic agent vanity wallet generation plus local registration storage.
It deliberately keeps attestation integration separate so the wallet identity
primitive can be tested without a live node.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


DEFAULT_DB_PATH = "/root/rustchain/rustchain_v2.db"
AGENT_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,19}$")
RESERVED_AGENT_NAMES = {
    "admin",
    "bank",
    "burn",
    "coinbase",
    "escrow",
    "founder",
    "genesis",
    "operator",
    "root",
    "system",
    "treasury",
}
MAX_VANITY_ATTEMPTS = 250_000


class AgentVanityError(ValueError):
    """Raised when an agent vanity wallet request is invalid."""


@dataclass(frozen=True)
class VanityWallet:
    agent_name: str
    wallet: str
    hardware_fingerprint_hash: str
    nonce: int
    vanity_digest: str
    public_key_hex: Optional[str] = None


def normalize_agent_name(agent_name: str) -> str:
    """Return the canonical vanity-name form or raise ``AgentVanityError``."""
    if not isinstance(agent_name, str):
        raise AgentVanityError("agent_name_must_be_text")
    normalized = agent_name.strip().lower().replace("_", "-")
    if not AGENT_NAME_RE.fullmatch(normalized):
        raise AgentVanityError("agent_name_must_be_3_to_20_alnum_dash")
    if normalized in RESERVED_AGENT_NAMES or normalized.startswith("rtc-"):
        raise AgentVanityError("agent_name_reserved")
    return normalized


def canonical_hardware_fingerprint(hardware_fingerprint: Mapping[str, Any] | str) -> str:
    """Return a stable SHA-256 hash for a hardware fingerprint payload."""
    if isinstance(hardware_fingerprint, Mapping):
        encoded = json.dumps(
            hardware_fingerprint,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    elif isinstance(hardware_fingerprint, str):
        text = hardware_fingerprint.strip()
        if not text:
            raise AgentVanityError("hardware_fingerprint_required")
        encoded = text.encode("utf-8")
    else:
        raise AgentVanityError("hardware_fingerprint_must_be_mapping_or_text")
    return hashlib.sha256(encoded).hexdigest()


def validate_public_key_hex(public_key_hex: Optional[str]) -> Optional[str]:
    """Validate an optional Ed25519 public key encoded as 32-byte hex."""
    if public_key_hex in (None, ""):
        return None
    if not isinstance(public_key_hex, str):
        raise AgentVanityError("public_key_must_be_hex_text")
    value = public_key_hex.strip().lower()
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise AgentVanityError("public_key_must_be_hex") from exc
    if len(raw) != 32:
        raise AgentVanityError("public_key_must_be_32_bytes")
    return value


def _seed_material(
    agent_name: str,
    hardware_hash: str,
    public_key_hex: Optional[str],
    nonce: int,
) -> bytes:
    payload = {
        "agent_name": agent_name,
        "hardware_fingerprint_hash": hardware_hash,
        "public_key_hex": public_key_hex or "",
        "nonce": nonce,
        "scheme": "rustchain-agent-vanity-v1",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_vanity_wallet(
    agent_name: str,
    hardware_fingerprint: Mapping[str, Any] | str,
    *,
    public_key_hex: Optional[str] = None,
    hash_prefix: str = "",
    hash_suffix: str = "",
    max_attempts: int = MAX_VANITY_ATTEMPTS,
) -> VanityWallet:
    """
    Generate ``RTC-<agent-name>-<hash>`` deterministically from agent identity
    and hardware fingerprint.

    Optional ``hash_prefix`` / ``hash_suffix`` constraints mine over a nonce
    against the derived hash portion. With no constraints, nonce 0 is returned.
    """
    normalized = normalize_agent_name(agent_name)
    hardware_hash = canonical_hardware_fingerprint(hardware_fingerprint)
    key_hex = validate_public_key_hex(public_key_hex)
    prefix = hash_prefix.lower().strip()
    suffix = hash_suffix.lower().strip()
    if not re.fullmatch(r"[0-9a-f]*", prefix + suffix):
        raise AgentVanityError("vanity_constraints_must_be_hex")
    if max_attempts < 1:
        raise AgentVanityError("max_attempts_must_be_positive")

    for nonce in range(max_attempts):
        digest = hashlib.sha256(_seed_material(normalized, hardware_hash, key_hex, nonce)).hexdigest()
        vanity_part = digest[:10]
        if vanity_part.startswith(prefix) and vanity_part.endswith(suffix):
            return VanityWallet(
                agent_name=normalized,
                wallet=f"RTC-{normalized}-{vanity_part}",
                hardware_fingerprint_hash=hardware_hash,
                nonce=nonce,
                vanity_digest=digest,
                public_key_hex=key_hex,
            )
    raise AgentVanityError("vanity_pattern_not_found")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_vanity_wallets (
    agent_name TEXT PRIMARY KEY,
    wallet TEXT NOT NULL UNIQUE,
    hardware_fingerprint_hash TEXT NOT NULL UNIQUE,
    public_key_hex TEXT,
    nonce INTEGER NOT NULL,
    vanity_digest TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_vanity_wallet ON agent_vanity_wallets(wallet);
CREATE INDEX IF NOT EXISTS idx_agent_vanity_hw ON agent_vanity_wallets(hardware_fingerprint_hash);
"""


def init_agent_vanity_tables(conn: sqlite3.Connection) -> None:
    """Create agent vanity registration tables."""
    conn.executescript(SCHEMA_SQL)


def register_agent_vanity_wallet(
    conn: sqlite3.Connection,
    agent_name: str,
    hardware_fingerprint: Mapping[str, Any] | str,
    *,
    public_key_hex: Optional[str] = None,
    hash_prefix: str = "",
    hash_suffix: str = "",
    now_ts: Optional[int] = None,
) -> VanityWallet:
    """Generate and persist a one-agent-per-machine vanity wallet registration."""
    init_agent_vanity_tables(conn)
    wallet = generate_vanity_wallet(
        agent_name,
        hardware_fingerprint,
        public_key_hex=public_key_hex,
        hash_prefix=hash_prefix,
        hash_suffix=hash_suffix,
    )
    now = int(time.time()) if now_ts is None else int(now_ts)
    existing = conn.execute(
        """
        SELECT agent_name, wallet, hardware_fingerprint_hash, public_key_hex, nonce, vanity_digest
        FROM agent_vanity_wallets
        WHERE agent_name = ? OR hardware_fingerprint_hash = ? OR wallet = ?
        """,
        (wallet.agent_name, wallet.hardware_fingerprint_hash, wallet.wallet),
    ).fetchone()
    if existing:
        row = _row_to_wallet(existing)
        if row == wallet:
            return row
        if row.agent_name == wallet.agent_name:
            raise AgentVanityError("agent_name_already_registered")
        if row.hardware_fingerprint_hash == wallet.hardware_fingerprint_hash:
            raise AgentVanityError("hardware_already_bound_to_agent")
        raise AgentVanityError("wallet_already_registered")

    conn.execute(
        """
        INSERT INTO agent_vanity_wallets (
            agent_name, wallet, hardware_fingerprint_hash, public_key_hex,
            nonce, vanity_digest, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wallet.agent_name,
            wallet.wallet,
            wallet.hardware_fingerprint_hash,
            wallet.public_key_hex,
            wallet.nonce,
            wallet.vanity_digest,
            now,
            now,
        ),
    )
    conn.commit()
    return wallet


def _row_to_wallet(row: Iterable[Any]) -> VanityWallet:
    values = list(row)
    return VanityWallet(
        agent_name=values[0],
        wallet=values[1],
        hardware_fingerprint_hash=values[2],
        public_key_hex=values[3],
        nonce=int(values[4]),
        vanity_digest=values[5],
    )


def get_agent_vanity_wallet(conn: sqlite3.Connection, agent_name: str) -> Optional[VanityWallet]:
    """Fetch a registration by agent name."""
    init_agent_vanity_tables(conn)
    normalized = normalize_agent_name(agent_name)
    row = conn.execute(
        """
        SELECT agent_name, wallet, hardware_fingerprint_hash, public_key_hex, nonce, vanity_digest
        FROM agent_vanity_wallets
        WHERE agent_name = ?
        """,
        (normalized,),
    ).fetchone()
    return _row_to_wallet(row) if row else None


def list_agent_vanity_wallets(conn: sqlite3.Connection) -> list[VanityWallet]:
    """List all registered agent vanity wallets in stable order."""
    init_agent_vanity_tables(conn)
    rows = conn.execute(
        """
        SELECT agent_name, wallet, hardware_fingerprint_hash, public_key_hex, nonce, vanity_digest
        FROM agent_vanity_wallets
        ORDER BY created_at ASC, agent_name ASC
        """
    ).fetchall()
    return [_row_to_wallet(row) for row in rows]


def _load_fingerprint_arg(value: str) -> Mapping[str, Any] | str:
    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return parsed if isinstance(parsed, Mapping) else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RustChain agent vanity wallet registration")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite DB path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="Generate a vanity wallet without saving it")
    gen.add_argument("agent_name")
    gen.add_argument("--fingerprint", required=True, help="JSON string, text seed, or JSON file path")
    gen.add_argument("--pubkey", dest="public_key_hex")
    gen.add_argument("--hash-prefix", default="")
    gen.add_argument("--hash-suffix", default="")

    reg = sub.add_parser("register", help="Generate and save a vanity wallet registration")
    reg.add_argument("agent_name")
    reg.add_argument("--fingerprint", required=True, help="JSON string, text seed, or JSON file path")
    reg.add_argument("--pubkey", dest="public_key_hex")
    reg.add_argument("--hash-prefix", default="")
    reg.add_argument("--hash-suffix", default="")

    sub.add_parser("list", help="List registered agent vanity wallets")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "generate":
        wallet = generate_vanity_wallet(
            args.agent_name,
            _load_fingerprint_arg(args.fingerprint),
            public_key_hex=args.public_key_hex,
            hash_prefix=args.hash_prefix,
            hash_suffix=args.hash_suffix,
        )
        print(json.dumps(asdict(wallet), sort_keys=True))
        return 0

    with sqlite3.connect(args.db) as conn:
        if args.cmd == "register":
            wallet = register_agent_vanity_wallet(
                conn,
                args.agent_name,
                _load_fingerprint_arg(args.fingerprint),
                public_key_hex=args.public_key_hex,
                hash_prefix=args.hash_prefix,
                hash_suffix=args.hash_suffix,
            )
            print(json.dumps(asdict(wallet), sort_keys=True))
            return 0
        if args.cmd == "list":
            wallets = [asdict(wallet) for wallet in list_agent_vanity_wallets(conn)]
            print(json.dumps(wallets, sort_keys=True))
            return 0
    raise AssertionError(f"unhandled command: {args.cmd}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
