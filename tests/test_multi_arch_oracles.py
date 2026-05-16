# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


def load_multi_arch_oracles():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "rips"
        / "rustchain-core"
        / "src"
        / "mutator_oracle"
        / "multi_arch_oracles.py"
    )
    spec = importlib.util.spec_from_file_location("multi_arch_oracles_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_mutation_seed_builds_hmac_ring_signature():
    multi_arch = load_multi_arch_oracles()
    ring = multi_arch.MultiArchOracleRing()
    ring.register_oracle(
        multi_arch.ArchitectureOracle(
            node_id="g4-node",
            hostname="g4.local",
            ip_address="192.0.2.10",
            architecture=multi_arch.CPUArchitecture.POWERPC_G4,
            cpu_model="PowerPC G4",
            simd_enabled=True,
        )
    )
    ring.register_oracle(
        multi_arch.ArchitectureOracle(
            node_id="x86-node",
            hostname="x86.local",
            ip_address="192.0.2.20",
            architecture=multi_arch.CPUArchitecture.INTEL_X86_64,
            cpu_model="Intel x86_64",
            simd_enabled=True,
        )
    )

    seed = ring.generate_mutation_seed(block_height=4852)

    assert seed is not None
    expected_signature = multi_arch.hmac.new(
        seed.seed,
        b"".join(
            arch_id.encode()
            for arch_id in sorted(seed.architecture_contributions.keys())
        ),
        multi_arch.hashlib.sha256,
    ).digest()
    assert seed.ring_signature == expected_signature
