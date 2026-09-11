"""Standalone runner: `python -m attractor` (from the `testing/` directory)."""

import sys

from attractor import examples  # noqa: F401  (registers the reference invariants)
from attractor.harness import run_all

sys.exit(run_all())
