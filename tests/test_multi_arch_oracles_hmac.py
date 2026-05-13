# SPDX-License-Identifier: MIT

import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "rips" / "rustchain-core" / "src" / "mutator_oracle" / "multi_arch_oracles.py"

spec = importlib.util.spec_from_file_location("multi_arch_oracles", MODULE_PATH)
multi_arch_oracles = importlib.util.module_from_spec(spec)
sys.modules["multi_arch_oracles"] = multi_arch_oracles
spec.loader.exec_module(multi_arch_oracles)


def test_generate_mutation_seed_uses_hmac_ring_signature_without_crashing():
    ring = multi_arch_oracles.MultiArchOracleRing()
    ring.register_oracle(
        multi_arch_oracles.ArchitectureOracle(
            node_id="g4-node",
            hostname="g4.local",
            ip_address="192.0.2.10",
            architecture=multi_arch_oracles.CPUArchitecture.POWERPC_G4,
            cpu_model="PowerPC G4",
            simd_enabled=True,
        )
    )
    ring.register_oracle(
        multi_arch_oracles.ArchitectureOracle(
            node_id="x86-node",
            hostname="x86.local",
            ip_address="192.0.2.11",
            architecture=multi_arch_oracles.CPUArchitecture.INTEL_X86_64,
            cpu_model="x86_64",
            simd_enabled=True,
        )
    )

    with patch.object(ring, "collect_entropy", side_effect=[b"a" * 64, b"b" * 64]):
        seed = ring.generate_mutation_seed(12345)

    assert seed is not None
    assert seed.ring_signature == hmac.new(
        seed.seed,
        b"ppc_g4x86_64",
        hashlib.sha256,
    ).digest()
