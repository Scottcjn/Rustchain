# SPDX-License-Identifier: MIT

import pytest

from slasher import (
    DOUBLE_PROPOSAL,
    DOUBLE_VOTE,
    SURROUND_VOTE,
    build_slashing_report,
    detect_double_proposals,
    detect_double_votes,
    detect_surround_votes,
    normalize_vote,
)


def test_detects_double_proposal_for_same_validator_and_slot():
    evidence = detect_double_proposals(
        [
            {"validator_id": "validator-a", "slot": 42, "block_root": "root-a"},
            {"validator_id": "validator-a", "slot": 42, "block_root": "root-b"},
            {"validator_id": "validator-b", "slot": 42, "block_root": "root-c"},
        ]
    )

    assert len(evidence) == 1
    assert evidence[0].offense == DOUBLE_PROPOSAL
    assert evidence[0].validator_id == "validator-a"
    assert evidence[0].first["block_root"] == "root-a"
    assert evidence[0].second["block_root"] == "root-b"


def test_ignores_duplicate_rebroadcast_of_same_proposal():
    evidence = detect_double_proposals(
        [
            {"validator_id": "validator-a", "slot": 42, "block_root": "root-a"},
            {"validator_id": "validator-a", "slot": 42, "block_root": "root-a"},
        ]
    )

    assert evidence == []


def test_detects_double_vote_for_same_target_epoch():
    evidence = detect_double_votes(
        [
            {
                "validator_id": "validator-a",
                "source_epoch": 4,
                "target_epoch": 5,
                "root": "root-a",
            },
            {
                "validator_id": "validator-a",
                "source_epoch": 4,
                "target_epoch": 5,
                "root": "root-b",
            },
        ]
    )

    assert len(evidence) == 1
    assert evidence[0].offense == DOUBLE_VOTE
    assert evidence[0].reason.startswith("validator voted for conflicting data")


def test_detects_surround_vote_interval():
    evidence = detect_surround_votes(
        [
            {
                "validator_id": "validator-a",
                "source_epoch": 2,
                "target_epoch": 8,
                "root": "outer",
            },
            {
                "validator_id": "validator-a",
                "source_epoch": 4,
                "target_epoch": 6,
                "root": "inner",
            },
        ]
    )

    assert len(evidence) == 1
    assert evidence[0].offense == SURROUND_VOTE
    assert evidence[0].first["root"] == "outer"
    assert evidence[0].second["root"] == "inner"


def test_ignores_non_overlapping_votes_and_other_validators():
    votes = [
        {
            "validator_id": "validator-a",
            "source_epoch": 2,
            "target_epoch": 4,
            "root": "root-a",
        },
        {
            "validator_id": "validator-a",
            "source_epoch": 4,
            "target_epoch": 6,
            "root": "root-b",
        },
        {
            "validator_id": "validator-b",
            "source_epoch": 3,
            "target_epoch": 5,
            "root": "root-c",
        },
    ]

    assert detect_double_votes(votes) == []
    assert detect_surround_votes(votes) == []


def test_build_slashing_report_summarizes_all_offenses():
    report = build_slashing_report(
        proposals=[
            {"validator_id": "validator-a", "slot": 7, "block_root": "p1"},
            {"validator_id": "validator-a", "slot": 7, "block_root": "p2"},
        ],
        votes=[
            {
                "validator_id": "validator-b",
                "source_epoch": 1,
                "target_epoch": 6,
                "root": "outer",
            },
            {
                "validator_id": "validator-b",
                "source_epoch": 3,
                "target_epoch": 4,
                "root": "inner",
            },
            {
                "validator_id": "validator-c",
                "source_epoch": 2,
                "target_epoch": 5,
                "root": "vote-a",
            },
            {
                "validator_id": "validator-c",
                "source_epoch": 2,
                "target_epoch": 5,
                "root": "vote-b",
            },
        ],
    )

    assert report["slashable"] is True
    assert report["evidence_count"] == 3
    assert report["validator_count"] == 3
    assert report["offense_counts"] == {
        DOUBLE_PROPOSAL: 1,
        DOUBLE_VOTE: 1,
        SURROUND_VOTE: 1,
    }


def test_invalid_vote_epoch_order_is_rejected():
    with pytest.raises(ValueError, match="target_epoch"):
        normalize_vote(
            {
                "validator_id": "validator-a",
                "source_epoch": 5,
                "target_epoch": 5,
                "root": "root-a",
            }
        )
