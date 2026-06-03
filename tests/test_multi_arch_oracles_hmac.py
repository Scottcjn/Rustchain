#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for multi-architecture oracle ring signatures."""

import contextlib
import hashlib
import hmac
import io
import sys
from pathlib import Path


MODULE_DIR = (
    Path(__file__).resolve().parents[1]
    / "rips"
    / "rustchain-core"
    / "src"
    / "mutator_oracle"
)
sys.path.insert(0, str(MODULE_DIR))

from multi_arch_oracles import (  # noqa: E402
    ArchitectureOracle,
    CPUArchitecture,
    MultiArchOracleRing,
)


def test_library_import_uses_hmac_for_ring_signature():
    ring = MultiArchOracleRing()

    with contextlib.redirect_stdout(io.StringIO()):
        assert ring.register_oracle(
            ArchitectureOracle(
                node_id="ppc",
                hostname="ppc.local",
                ip_address="127.0.0.1",
                architecture=CPUArchitecture.POWERPC_G4,
                cpu_model="PowerMac G4",
                simd_enabled=True,
            )
        )
        assert ring.register_oracle(
            ArchitectureOracle(
                node_id="x86",
                hostname="x86.local",
                ip_address="127.0.0.2",
                architecture=CPUArchitecture.INTEL_X86_64,
                cpu_model="x86_64",
                simd_enabled=True,
            )
        )
        seed = ring.generate_mutation_seed(block_height=123)

    assert seed is not None
    arch_message = b"".join(
        arch.encode() for arch in sorted(seed.architecture_contributions)
    )
    expected_hmac = hmac.new(seed.seed, arch_message, hashlib.sha256).digest()
    fallback_sha256 = hashlib.sha256(seed.seed).digest()

    assert seed.ring_signature == expected_hmac
    assert seed.ring_signature != fallback_sha256
