# SPDX-License-Identifier: MIT
"""Regression coverage for first-class RISC-V CPU detection."""

import sys

sys.path.insert(0, ".")

import cpu_architecture_detection as modern_cpu
import cpu_vintage_architectures as vintage_cpu


def test_vintage_detection_sifive_u74():
    assert vintage_cpu.detect_vintage_architecture("SiFive U74 RISC-V rv64gc") == (
        "riscv",
        "riscv_sifive_u74",
        2020,
        1.5,
    )


def test_vintage_detection_starfive_jh7110():
    assert vintage_cpu.detect_vintage_architecture("StarFive JH7110 VisionFive 2") == (
        "riscv",
        "riscv_starfive_jh7110",
        2022,
        1.4,
    )


def test_vintage_detection_allwinner_d1_c906():
    assert vintage_cpu.detect_vintage_architecture("Allwinner D1 T-Head C906") == (
        "riscv",
        "riscv_allwinner_d1",
        2021,
        1.4,
    )


def test_vintage_detection_generic_rv64gc():
    assert vintage_cpu.detect_vintage_architecture("isa : rv64imafdc") == (
        "riscv",
        "riscv_generic",
        2014,
        1.4,
    )


def test_modern_detection_sifive_u74():
    assert modern_cpu.detect_cpu_architecture("SiFive U74 RISC-V rv64gc") == (
        "riscv",
        "riscv_sifive_u74",
        2020,
        False,
    )


def test_modern_detection_generic_riscv64():
    assert modern_cpu.detect_cpu_architecture("riscv64 rv64gc") == (
        "riscv",
        "rv64gc",
        2015,
        False,
    )


def test_modern_detection_misa_vector_extension_marker():
    assert modern_cpu.detect_cpu_architecture("misa: rv64gcv") == (
        "riscv",
        "rv64gcv",
        2021,
        False,
    )


def test_modern_detection_rvtest_signature():
    assert modern_cpu.detect_cpu_architecture("rvtest signature: riscv64") == (
        "riscv",
        "rv64gc",
        2015,
        False,
    )


def test_riscv_description_and_multiplier():
    info = modern_cpu.calculate_antiquity_multiplier(
        "StarFive JH7110 RISC-V rv64gc",
        custom_year=2024,
    )

    assert info.vendor == "riscv"
    assert info.architecture == "riscv_starfive_jh7110"
    assert info.generation == "RISC-V StarFive JH7110"
    assert info.antiquity_multiplier == 1.4
