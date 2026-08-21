"""Attractor: reusable adversarial test harness for RustChain consensus invariants."""

from .harness import (  # noqa: F401
    REGISTRY,
    Adversary,
    Ctx,
    HarnessUsageError,
    InvariantSpec,
    InvariantViolation,
    invariant,
    run_all,
)

__all__ = [
    "REGISTRY",
    "Adversary",
    "Ctx",
    "HarnessUsageError",
    "InvariantSpec",
    "InvariantViolation",
    "invariant",
    "run_all",
]
