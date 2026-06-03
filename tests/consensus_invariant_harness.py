#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Small metadata wrapper for consensus invariant attractor tests."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ConsensusInvariantCase:
    """A single deterministic consensus invariant and its executable oracle."""

    invariant_id: str
    statement: str
    fixture: str
    adversarial_move: str
    oracle: Callable[[], None]

    def validate(self) -> None:
        missing = [
            field
            for field in ("invariant_id", "statement", "fixture", "adversarial_move")
            if not getattr(self, field).strip()
        ]
        if missing:
            raise AssertionError(f"invariant case is missing required fields: {missing}")


def assert_consensus_invariant(case: ConsensusInvariantCase) -> None:
    """Validate the invariant metadata, then execute its deterministic oracle."""

    case.validate()
    case.oracle()
