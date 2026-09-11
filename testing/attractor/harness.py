"""Attractor consensus-invariant harness.

A tiny, dependency-free harness that gives contributors a single, uniform way to
submit *one invariant per test* against RustChain consensus behaviour.

Grammar (enforced by :func:`invariant` and :func:`check`):

    @invariant(
        id="INV-EMISSION-001",              # stable, unique, uppercase id
        statement="rewards minted per epoch == declared emission",
        scope="consensus/emission",
        adversarial=True,                   # test must include a hostile case
    )
    def test_something(ctx):
        ctx.check(actual == expected, "why this pins the invariant")

Design goals
------------
* Deterministic: the harness seeds its own RNG; no wall-clock, no network.
* Self-contained: pure stdlib, importable from pytest or run standalone.
* Objectively reviewable: every registered invariant carries machine-checkable
  metadata, so the acceptance rubric in README.md can be applied mechanically.
"""

from __future__ import annotations

import random
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

ID_RE = re.compile(r"^INV-[A-Z0-9]+(-[A-Z0-9]+)*-\d{3}$")

REGISTRY: Dict[str, "InvariantSpec"] = {}


class InvariantViolation(AssertionError):
    """Raised when an invariant assertion fails."""


class HarnessUsageError(ValueError):
    """Raised when a submission violates the submission grammar."""


@dataclass(frozen=True)
class InvariantSpec:
    id: str
    statement: str
    scope: str
    adversarial: bool
    func: Callable[["Ctx"], None]


@dataclass
class Ctx:
    """Execution context handed to every invariant test."""

    spec: InvariantSpec
    seed: int = 1337
    rng: random.Random = field(init=False)
    checks: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def check(self, condition: bool, reason: str) -> None:
        """Assert one fact that supports the invariant."""
        if not reason or len(reason) < 8:
            raise HarnessUsageError("ctx.check() requires a descriptive reason")
        self.checks.append(reason)
        if not condition:
            raise InvariantViolation(
                f"{self.spec.id} violated: {self.spec.statement} :: {reason}"
            )

    def adversary(self, name: str) -> "Adversary":
        return Adversary(name, self.rng)


@dataclass
class Adversary:
    """Small helper to make the hostile intent of a test explicit."""

    name: str
    rng: random.Random

    def replay(self, items: List[Any], times: int = 2) -> List[Any]:
        """Duplicate every item `times` times (replay / double-submit attack)."""
        return [x for x in items for _ in range(times)]

    def shuffle(self, items: List[Any]) -> List[Any]:
        out = list(items)
        self.rng.shuffle(out)
        return out

    def inject(self, items: List[Any], payload: Any, count: int = 1) -> List[Any]:
        out = list(items)
        for _ in range(count):
            out.insert(self.rng.randrange(len(out) + 1), payload)
        return out


def invariant(*, id: str, statement: str, scope: str, adversarial: bool = True):
    """Register exactly one invariant. Enforces the submission grammar."""

    def deco(func: Callable[[Ctx], None]) -> Callable[..., None]:
        if not ID_RE.match(id):
            raise HarnessUsageError(
                f"invariant id {id!r} must match INV-<AREA>-<NNN> (uppercase)"
            )
        if id in REGISTRY:
            raise HarnessUsageError(f"duplicate invariant id {id!r}")
        if len(statement) < 15:
            raise HarnessUsageError("statement must describe the invariant precisely")
        if "/" not in scope:
            raise HarnessUsageError("scope must look like 'area/subarea'")
        spec = InvariantSpec(id, statement, scope, adversarial, func)
        REGISTRY[id] = spec

        def wrapper(*_args: Any, **_kwargs: Any) -> None:
            ctx = Ctx(spec)
            func(ctx)
            if not ctx.checks:
                raise HarnessUsageError(f"{id} performed no ctx.check() calls")

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = f"[{id}] {statement}"
        wrapper.invariant_spec = spec  # type: ignore[attr-defined]
        return wrapper

    return deco


def run_all() -> int:
    """Standalone runner: `python -m attractor.harness`. Returns exit code."""
    failures = 0
    for spec in REGISTRY.values():
        ctx = Ctx(spec)
        try:
            spec.func(ctx)
            if not ctx.checks:
                raise HarnessUsageError(f"{spec.id} performed no ctx.check() calls")
            print(f"PASS {spec.id}  {spec.statement}")
        except Exception as exc:  # noqa: BLE001 - report, don't crash the suite
            failures += 1
            print(f"FAIL {spec.id}  {exc}")
    print(f"\n{len(REGISTRY) - failures}/{len(REGISTRY)} invariants green")
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    print("run the suite with: python -m attractor", file=sys.stderr)
    sys.exit(2)
