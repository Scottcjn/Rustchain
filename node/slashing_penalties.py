#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Slashing penalty core for validator equivocation evidence.

This module applies an already-verified slashable offense to local ledger state:
it records the evidence idempotently, burns part of the validator balance, and
marks the validator as ineligible for future epochs.
"""

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

URTC_PER_RTC = 1_000_000
DEFAULT_SLASH_FRACTION = 0.10
DEFAULT_EXCLUSION_EPOCHS = 2
SLASHABLE_OFFENSES = frozenset(
    {
        "double_vote",
        "double_proposal",
        "equivocation",
        "surround_vote",
    }
)


class SlashingError(ValueError):
    """Raised when slashing evidence or penalty parameters are invalid."""


@dataclass(frozen=True)
class SlashingEvidence:
    validator_id: str
    offense_type: str
    epoch: int
    evidence_hash: str
    details: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "validator_id": self.validator_id,
                "offense_type": self.offense_type,
                "epoch": self.epoch,
                "evidence_hash": self.evidence_hash,
                "details": self.details,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def normalize_slashing_evidence(
    evidence: Union[SlashingEvidence, Mapping[str, Any]]
) -> SlashingEvidence:
    """Normalize mapping/dataclass evidence through one validation path."""
    if isinstance(evidence, SlashingEvidence):
        payload = {
            "validator_id": evidence.validator_id,
            "offense_type": evidence.offense_type,
            "epoch": evidence.epoch,
            "evidence_hash": evidence.evidence_hash,
            "details": evidence.details,
        }
    elif isinstance(evidence, Mapping):
        payload = dict(evidence)
    else:
        raise SlashingError("evidence_must_be_mapping")

    validator_id = _required_text(payload.get("validator_id"), "validator_id")
    offense_type = _required_text(payload.get("offense_type"), "offense_type")
    if offense_type not in SLASHABLE_OFFENSES:
        raise SlashingError("unsupported_offense_type")

    epoch = _required_int(payload.get("epoch"), "epoch")
    if epoch < 0:
        raise SlashingError("epoch_must_be_non_negative")

    details = payload["details"] if "details" in payload else {}
    if not isinstance(details, Mapping):
        raise SlashingError("details_must_be_mapping")
    details = dict(details)

    evidence_hash = payload.get("evidence_hash")
    if evidence_hash is None:
        evidence_hash = _derive_evidence_hash(validator_id, offense_type, epoch, details)
    evidence_hash = _required_text(evidence_hash, "evidence_hash")

    return SlashingEvidence(
        validator_id=validator_id,
        offense_type=offense_type,
        epoch=epoch,
        evidence_hash=evidence_hash,
        details=details,
    )


def ensure_slashing_tables(conn: sqlite3.Connection) -> None:
    """Create slashing tables when a legacy node DB does not have them yet."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS validator_slashes (
            evidence_hash TEXT PRIMARY KEY,
            validator_id TEXT NOT NULL,
            offense_type TEXT NOT NULL,
            epoch INTEGER NOT NULL,
            penalty_urtc INTEGER NOT NULL,
            slashed_until_epoch INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS slashed_validators (
            validator_id TEXT PRIMARY KEY,
            slashed_until_epoch INTEGER NOT NULL,
            total_penalty_urtc INTEGER NOT NULL DEFAULT 0,
            last_offense_type TEXT NOT NULL,
            last_slashed_at INTEGER NOT NULL
        )
        """
    )


def apply_slashing_evidence(
    conn: sqlite3.Connection,
    evidence: Union[SlashingEvidence, Mapping[str, Any]],
    *,
    current_epoch: Optional[int] = None,
    slash_fraction: float = DEFAULT_SLASH_FRACTION,
    min_penalty_urtc: int = 1,
    exclusion_epochs: int = DEFAULT_EXCLUSION_EPOCHS,
    now_ts: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Apply one slashable offense idempotently.

    The evidence hash is the idempotency key. Replaying the same evidence returns
    ``duplicate=True`` and does not burn funds again.
    """
    normalized = normalize_slashing_evidence(evidence)
    current_epoch = normalized.epoch if current_epoch is None else _required_int(current_epoch, "current_epoch")
    if current_epoch < normalized.epoch:
        raise SlashingError("current_epoch_before_evidence_epoch")
    if not 0 < slash_fraction <= 1:
        raise SlashingError("slash_fraction_out_of_range")
    if min_penalty_urtc < 0:
        raise SlashingError("min_penalty_urtc_must_be_non_negative")
    if exclusion_epochs < 1:
        raise SlashingError("exclusion_epochs_must_be_positive")

    ensure_slashing_tables(conn)
    existing = conn.execute(
        "SELECT penalty_urtc, slashed_until_epoch FROM validator_slashes WHERE evidence_hash = ?",
        (normalized.evidence_hash,),
    ).fetchone()
    if existing:
        return {
            "applied": False,
            "duplicate": True,
            "validator_id": normalized.validator_id,
            "offense_type": normalized.offense_type,
            "penalty_urtc": int(existing[0]),
            "slashed_until_epoch": int(existing[1]),
            "evidence_hash": normalized.evidence_hash,
        }

    balance = _get_balance_urtc(conn, normalized.validator_id)
    penalty = _calculate_penalty_urtc(balance, slash_fraction, min_penalty_urtc)
    if penalty:
        _debit_balance(conn, normalized.validator_id, penalty)

    slashed_until = current_epoch + exclusion_epochs
    now_ts = int(time.time()) if now_ts is None else _required_int(now_ts, "now_ts")
    conn.execute(
        """
        INSERT INTO validator_slashes (
            evidence_hash, validator_id, offense_type, epoch, penalty_urtc,
            slashed_until_epoch, evidence_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized.evidence_hash,
            normalized.validator_id,
            normalized.offense_type,
            normalized.epoch,
            penalty,
            slashed_until,
            normalized.to_json(),
            now_ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO slashed_validators (
            validator_id, slashed_until_epoch, total_penalty_urtc,
            last_offense_type, last_slashed_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(validator_id) DO UPDATE SET
            slashed_until_epoch = MAX(slashed_until_epoch, excluded.slashed_until_epoch),
            total_penalty_urtc = total_penalty_urtc + excluded.total_penalty_urtc,
            last_offense_type = excluded.last_offense_type,
            last_slashed_at = excluded.last_slashed_at
        """,
        (normalized.validator_id, slashed_until, penalty, normalized.offense_type, now_ts),
    )
    removed_enrollments = _remove_future_enrollments(
        conn, normalized.validator_id, current_epoch, slashed_until
    )

    return {
        "applied": True,
        "duplicate": False,
        "validator_id": normalized.validator_id,
        "offense_type": normalized.offense_type,
        "penalty_urtc": penalty,
        "balance_before_urtc": balance,
        "balance_after_urtc": max(0, balance - penalty),
        "slashed_until_epoch": slashed_until,
        "removed_future_enrollments": removed_enrollments,
        "evidence_hash": normalized.evidence_hash,
    }


def is_validator_slashed(conn: sqlite3.Connection, validator_id: str, epoch: int) -> bool:
    """Return whether a validator is excluded for the given epoch."""
    ensure_slashing_tables(conn)
    validator_id = _required_text(validator_id, "validator_id")
    epoch = _required_int(epoch, "epoch")
    row = conn.execute(
        """
        SELECT 1 FROM slashed_validators
        WHERE validator_id = ? AND slashed_until_epoch >= ?
        LIMIT 1
        """,
        (validator_id, epoch),
    ).fetchone()
    return row is not None


def filter_slashed_validators(
    conn: sqlite3.Connection,
    validator_ids: Iterable[str],
    epoch: int,
) -> List[str]:
    """Filter an enrollment/validator candidate list against active slashes."""
    return [
        validator_id
        for validator_id in validator_ids
        if not is_validator_slashed(conn, validator_id, epoch)
    ]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SlashingError(f"{field}_must_be_non_empty_text")
    return value.strip()


def _required_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SlashingError(f"{field}_must_be_integer")
    return value


def _derive_evidence_hash(
    validator_id: str,
    offense_type: str,
    epoch: int,
    details: Mapping[str, Any],
) -> str:
    payload = json.dumps(
        {
            "validator_id": validator_id,
            "offense_type": offense_type,
            "epoch": epoch,
            "details": details,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _calculate_penalty_urtc(balance_urtc: int, slash_fraction: float, min_penalty_urtc: int) -> int:
    if balance_urtc <= 0:
        return 0
    fraction_penalty = int(balance_urtc * slash_fraction)
    return min(balance_urtc, max(min_penalty_urtc, fraction_penalty))


def _get_balance_urtc(conn: sqlite3.Connection, validator_id: str) -> int:
    if not _table_exists(conn, "balances"):
        return 0
    columns = _table_columns(conn, "balances")
    key_column = _first_present(columns, ("miner_id", "miner_pk", "wallet", "validator_id"))
    if not key_column:
        return 0
    if "amount_i64" in columns:
        row = conn.execute(
            f"SELECT amount_i64 FROM balances WHERE {key_column} = ?",
            (validator_id,),
        ).fetchone()
        return max(0, int(row[0])) if row else 0
    if "balance_rtc" in columns:
        row = conn.execute(
            f"SELECT balance_rtc FROM balances WHERE {key_column} = ?",
            (validator_id,),
        ).fetchone()
        return max(0, int(float(row[0]) * URTC_PER_RTC)) if row else 0
    return 0


def _debit_balance(conn: sqlite3.Connection, validator_id: str, penalty_urtc: int) -> None:
    columns = _table_columns(conn, "balances")
    key_column = _first_present(columns, ("miner_id", "miner_pk", "wallet", "validator_id"))
    if not key_column:
        return
    if "amount_i64" in columns:
        conn.execute(
            f"""
            UPDATE balances
            SET amount_i64 = CASE
                WHEN amount_i64 >= ? THEN amount_i64 - ?
                ELSE 0
            END
            WHERE {key_column} = ?
            """,
            (penalty_urtc, penalty_urtc, validator_id),
        )
    elif "balance_rtc" in columns:
        penalty_rtc = penalty_urtc / URTC_PER_RTC
        conn.execute(
            f"""
            UPDATE balances
            SET balance_rtc = CASE
                WHEN balance_rtc >= ? THEN balance_rtc - ?
                ELSE 0
            END
            WHERE {key_column} = ?
            """,
            (penalty_rtc, penalty_rtc, validator_id),
        )


def _remove_future_enrollments(
    conn: sqlite3.Connection,
    validator_id: str,
    current_epoch: int,
    slashed_until_epoch: int,
) -> int:
    if not _table_exists(conn, "epoch_enroll"):
        return 0
    columns = _table_columns(conn, "epoch_enroll")
    key_column = _first_present(columns, ("miner_pk", "validator_id", "miner_id"))
    if not key_column or "epoch" not in columns:
        return 0
    cursor = conn.execute(
        f"""
        DELETE FROM epoch_enroll
        WHERE {key_column} = ?
          AND epoch > ?
          AND epoch <= ?
        """,
        (validator_id, current_epoch, slashed_until_epoch),
    )
    return cursor.rowcount


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> Sequence[str]:
    return tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall())


def _first_present(columns: Sequence[str], candidates: Tuple[str, ...]) -> Optional[str]:
    column_set = set(columns)
    for candidate in candidates:
        if candidate in column_set:
            return candidate
    return None
