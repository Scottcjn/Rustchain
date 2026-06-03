# SPDX-License-Identifier: MIT
"""
Slashing evidence helpers for RustChain validator/proposer duties.

The module is intentionally side-effect free: callers can feed locally observed
votes and proposals, then decide how to persist or submit the generated report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Sequence, Tuple, Union


DOUBLE_PROPOSAL = "double_proposal"
DOUBLE_VOTE = "double_vote"
SURROUND_VOTE = "surround_vote"


@dataclass(frozen=True)
class VoteRecord:
    """Observed validator vote over a source/target epoch interval."""

    validator_id: str
    source_epoch: int
    target_epoch: int
    root: str
    signature: str = ""


@dataclass(frozen=True)
class ProposalRecord:
    """Observed block proposal for one slot."""

    validator_id: str
    slot: int
    block_root: str
    signature: str = ""


@dataclass(frozen=True)
class SlashingEvidence:
    """Pair of conflicting records that can be included in a slashing report."""

    offense: str
    validator_id: str
    first: Dict[str, object]
    second: Dict[str, object]
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


VoteInput = Union[VoteRecord, Dict[str, object]]
ProposalInput = Union[ProposalRecord, Dict[str, object]]


def _as_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _as_non_empty_str(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def normalize_vote(record: VoteInput) -> VoteRecord:
    """Normalize mapping/dataclass vote input and validate epoch ordering."""
    if isinstance(record, VoteRecord):
        data: Mapping[str, object] = asdict(record)
    else:
        if not isinstance(record, Mapping):
            raise ValueError("vote record must be a mapping or VoteRecord")
        data = record
    vote = VoteRecord(
        validator_id=_as_non_empty_str(data.get("validator_id"), "validator_id"),
        source_epoch=_as_int(data.get("source_epoch"), "source_epoch"),
        target_epoch=_as_int(data.get("target_epoch"), "target_epoch"),
        root=_as_non_empty_str(data.get("root"), "root"),
        signature=str(data.get("signature") or ""),
    )

    if vote.target_epoch <= vote.source_epoch:
        raise ValueError("target_epoch must be greater than source_epoch")
    return vote


def normalize_proposal(record: ProposalInput) -> ProposalRecord:
    """Normalize mapping/dataclass proposal input."""
    if isinstance(record, ProposalRecord):
        data: Mapping[str, object] = asdict(record)
    else:
        if not isinstance(record, Mapping):
            raise ValueError("proposal record must be a mapping or ProposalRecord")
        data = record
    proposal = ProposalRecord(
        validator_id=_as_non_empty_str(data.get("validator_id"), "validator_id"),
        slot=_as_int(data.get("slot"), "slot"),
        block_root=_as_non_empty_str(data.get("block_root"), "block_root"),
        signature=str(data.get("signature") or ""),
    )

    if proposal.slot < 0:
        raise ValueError("slot must be non-negative")
    return proposal


def detect_double_proposals(proposals: Iterable[ProposalInput]) -> List[SlashingEvidence]:
    """Detect two different block proposals by the same validator in one slot."""
    by_validator_slot: Dict[Tuple[str, int], ProposalRecord] = {}
    evidence: List[SlashingEvidence] = []

    for item in proposals:
        proposal = normalize_proposal(item)
        key = (proposal.validator_id, proposal.slot)
        previous = by_validator_slot.get(key)
        if previous is None:
            by_validator_slot[key] = proposal
            continue
        if previous.block_root == proposal.block_root:
            continue
        evidence.append(
            SlashingEvidence(
                offense=DOUBLE_PROPOSAL,
                validator_id=proposal.validator_id,
                first=asdict(previous),
                second=asdict(proposal),
                reason="validator proposed different block roots for the same slot",
            )
        )

    return evidence


def detect_double_votes(votes: Iterable[VoteInput]) -> List[SlashingEvidence]:
    """Detect two different votes by the same validator for one target epoch."""
    by_validator_target: Dict[Tuple[str, int], VoteRecord] = {}
    evidence: List[SlashingEvidence] = []

    for item in votes:
        vote = normalize_vote(item)
        key = (vote.validator_id, vote.target_epoch)
        previous = by_validator_target.get(key)
        if previous is None:
            by_validator_target[key] = vote
            continue
        if previous.root == vote.root and previous.source_epoch == vote.source_epoch:
            continue
        evidence.append(
            SlashingEvidence(
                offense=DOUBLE_VOTE,
                validator_id=vote.validator_id,
                first=asdict(previous),
                second=asdict(vote),
                reason="validator voted for conflicting data at the same target epoch",
            )
        )

    return evidence


def _is_surrounding_vote(first: VoteRecord, second: VoteRecord) -> bool:
    return (
        first.validator_id == second.validator_id
        and first.source_epoch < second.source_epoch
        and second.target_epoch < first.target_epoch
    )


def detect_surround_votes(votes: Iterable[VoteInput]) -> List[SlashingEvidence]:
    """Detect source/target intervals where one vote surrounds another."""
    normalized = [normalize_vote(item) for item in votes]
    evidence: List[SlashingEvidence] = []

    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1 :]:
            if _is_surrounding_vote(left, right):
                first, second = left, right
            elif _is_surrounding_vote(right, left):
                first, second = right, left
            else:
                continue
            evidence.append(
                SlashingEvidence(
                    offense=SURROUND_VOTE,
                    validator_id=first.validator_id,
                    first=asdict(first),
                    second=asdict(second),
                    reason="validator cast a vote whose source/target interval surrounds another vote",
                )
            )

    return evidence


def build_slashing_report(
    *,
    votes: Sequence[VoteInput] = (),
    proposals: Sequence[ProposalInput] = (),
) -> Dict[str, object]:
    """Build a deterministic report for all slashable offenses in the inputs."""
    evidence = (
        detect_double_proposals(proposals)
        + detect_double_votes(votes)
        + detect_surround_votes(votes)
    )
    evidence.sort(
        key=lambda item: (
            item.validator_id,
            item.offense,
            str(item.first),
            str(item.second),
        )
    )

    counts: Dict[str, int] = {
        DOUBLE_PROPOSAL: 0,
        DOUBLE_VOTE: 0,
        SURROUND_VOTE: 0,
    }
    validators = set()
    for item in evidence:
        counts[item.offense] += 1
        validators.add(item.validator_id)

    return {
        "slashable": bool(evidence),
        "evidence_count": len(evidence),
        "validator_count": len(validators),
        "offense_counts": counts,
        "evidence": [item.to_dict() for item in evidence],
    }
