import sqlite3

import pytest
from slashing_penalties import (
    SlashingError,
    SlashingEvidence,
    apply_slashing_evidence,
    filter_slashed_validators,
    is_validator_slashed,
    normalize_slashing_evidence,
)


def _evidence(**overrides):
    data = {
        "validator_id": "validator-a",
        "offense_type": "double_vote",
        "epoch": 10,
        "details": {"vote_a": "root-a", "vote_b": "root-b"},
    }
    data.update(overrides)
    return data


def test_apply_slashing_evidence_burns_balance_and_excludes_future_epochs():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
        CREATE TABLE epoch_enroll (epoch INTEGER NOT NULL, miner_pk TEXT NOT NULL, weight REAL NOT NULL, PRIMARY KEY (epoch, miner_pk));
        INSERT INTO balances(miner_id, amount_i64) VALUES ('validator-a', 1000000);
        INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES
            (10, 'validator-a', 1.0),
            (11, 'validator-a', 1.0),
            (12, 'validator-a', 1.0),
            (13, 'validator-a', 1.0),
            (14, 'validator-a', 1.0);
        """
    )

    result = apply_slashing_evidence(conn, _evidence(), current_epoch=10, slash_fraction=0.25, exclusion_epochs=3, now_ts=1234)

    assert result["applied"] is True
    assert result["penalty_urtc"] == 250000
    assert result["slashed_until_epoch"] == 13
    assert result["removed_future_enrollments"] == 3
    assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id='validator-a'").fetchone()[0] == 750000
    assert conn.execute("SELECT epoch FROM epoch_enroll ORDER BY epoch").fetchall() == [(10,), (14,)]
    assert is_validator_slashed(conn, "validator-a", 13) is True
    assert is_validator_slashed(conn, "validator-a", 14) is False
    assert filter_slashed_validators(conn, ["validator-a", "validator-b"], 11) == ["validator-b"]


def test_slashing_evidence_is_idempotent_by_evidence_hash():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
        INSERT INTO balances(miner_id, amount_i64) VALUES ('validator-a', 1000000);
        """
    )
    evidence = _evidence(evidence_hash="same-proof")

    first = apply_slashing_evidence(conn, evidence, now_ts=1234)
    second = apply_slashing_evidence(conn, evidence, now_ts=1235)

    assert first["applied"] is True
    assert second["applied"] is False
    assert second["duplicate"] is True
    assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id='validator-a'").fetchone()[0] == 900000
    assert conn.execute("SELECT COUNT(*) FROM validator_slashes").fetchone()[0] == 1


def test_balance_rtc_schema_is_supported_for_legacy_tables():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL);
        INSERT INTO balances(miner_pk, balance_rtc) VALUES ('validator-a', 2.5);
        """
    )

    result = apply_slashing_evidence(conn, _evidence(offense_type="equivocation"), slash_fraction=0.5, now_ts=1234)

    assert result["penalty_urtc"] == 1250000
    assert conn.execute("SELECT balance_rtc FROM balances WHERE miner_pk='validator-a'").fetchone()[0] == 1.25


def test_dataclass_evidence_uses_same_validation_path_as_mapping():
    with pytest.raises(SlashingError, match="validator_id_must_be_non_empty_text"):
        normalize_slashing_evidence(
            SlashingEvidence(validator_id="", offense_type="double_vote", epoch=10, evidence_hash="proof", details={})
        )


@pytest.mark.parametrize(
    "bad_evidence, error",
    [
        (_evidence(offense_type="not-slashable"), "unsupported_offense_type"),
        (_evidence(epoch=True), "epoch_must_be_integer"),
        (_evidence(details=[]), "details_must_be_mapping"),
    ],
)
def test_invalid_evidence_is_rejected(bad_evidence, error):
    with pytest.raises(SlashingError, match=error):
        normalize_slashing_evidence(bad_evidence)
